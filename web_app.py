# -*- coding: utf-8 -*-

import json
import signal
import sys
import time
import threading

import cv2
import numpy as np
from flask import Flask, render_template, Response, stream_with_context, request

from config import Config
from camera import Camera
from analyzer import Analyzer
from logger import SessionLogger
from guidance import generate_guidance

cfg = Config()
camera = None
analyzer = None
logger = None

latest_frame = None
latest_result = None
history = []
analysis_count = 0
frame_count = 0
vllm_ready = False
collection_progress = 0.0
collection_state = "idle"
monitor_start_time = None

_face_cascade = None
_face_cascade_lock = threading.Lock()
_state_lock = threading.Lock()


def _get_face_cascade():
    global _face_cascade
    if _face_cascade is None:
        with _face_cascade_lock:
            if _face_cascade is None:
                path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                _face_cascade = cv2.CascadeClassifier(path)
    return _face_cascade

_frame_lock = threading.Lock()
_result_lock = threading.Lock()
_history_lock = threading.Lock()

app = Flask(__name__)


def capture_loop():
    global latest_frame, frame_count
    while camera:
        frame = camera.read()
        if frame is not None:
            with _frame_lock:
                latest_frame = frame
                frame_count = camera.frame_count


def connect_vllm():
    global analyzer, vllm_ready, logger
    analyzer = Analyzer(cfg)
    while camera:
        if analyzer.check_health():
            with _state_lock:
                vllm_ready = True
            print(f"[+] vLLM connected: {cfg.model_name}")
            logger = SessionLogger(cfg.log_dir)
            return
        print("[-] vLLM not ready, retry in 5s...")
        time.sleep(5)


def gen_mjpeg():
    sw, sh = cfg.stream_width, cfg.stream_height
    cascade = _get_face_cascade()
    placeholder = None
    while True:
        try:
            with _frame_lock:
                f = latest_frame.copy() if latest_frame is not None else None
            if f is not None:
                if f.shape[1] != sw or f.shape[0] != sh:
                    f = cv2.resize(f, (sw, sh), interpolation=cv2.INTER_LINEAR)
                _draw_face_guide(f, cascade)
                ret, jpeg = cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ret:
                    yield (b"--frame\r\n"
                           b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
            else:
                if placeholder is None:
                    placeholder = _make_placeholder(sw, sh)
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + placeholder + b"\r\n")
        except GeneratorExit:
            break
        except Exception:
            if placeholder is None:
                placeholder = _make_placeholder(sw, sh)
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + placeholder + b"\r\n")
        time.sleep(0.03)


def _make_placeholder(w, h):
    img = np.zeros((h, w, 3), dtype=np.uint8)
    cv2.putText(img, "Camera starting...", (w // 2 - 100, h // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 100, 100), 1)
    _, jpeg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 60])
    return jpeg.tobytes()


def _get_ellipse_params(w, h):
    d = min(w, h)
    cx, cy = w // 2, h // 2
    axes = (int(d * 0.30), int(d * 0.35))
    return cx, cy, axes


def _draw_face_guide(frame, cascade):
    h, w = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))

    cx, cy, axes = _get_ellipse_params(w, h)

    is_good = False
    if len(faces) > 0:
        best_face = None
        best_dist = float("inf")
        for (fx, fy, fw, fh) in faces:
            fc_x, fc_y = fx + fw // 2, fy + fh // 2
            dist = (fc_x - cx) ** 2 + (fc_y - cy) ** 2
            if dist < best_dist:
                best_dist = dist
                best_face = (fx, fy, fw, fh)

        if best_face is not None:
            fx, fy, fw, fh = best_face
            fc_x, fc_y = fx + fw // 2, fy + fh // 2
            inside = ((fc_x - cx) / axes[0]) ** 2 + ((fc_y - cy) / axes[1]) ** 2 < 0.7
            area_ratio = (fw * fh) / (3.14 * axes[0] * axes[1])
            good_size = 0.3 < area_ratio < 0.85
            is_good = inside and good_size

    blurred = cv2.GaussianBlur(frame, (31, 31), 15)
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.ellipse(mask, (cx, cy), axes, 0, 0, 360, 255, -1)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.erode(mask, kernel, iterations=1)

    inv_mask = cv2.bitwise_not(mask)
    face_area = cv2.bitwise_and(frame, frame, mask=mask)
    blur_area = cv2.bitwise_and(blurred, blurred, mask=inv_mask)
    result = cv2.add(face_area, blur_area)

    color = (0, 255, 0) if is_good else (255, 255, 255)
    cv2.ellipse(result, (cx, cy), axes, 0, 0, 360, color, 2)

    if is_good:
        _put_cn_text(result, "\u2713 \u9A8C\u8BC1\u901A\u8FC7", cx - 55, cy + axes[1] + 22, (0, 255, 0))

    frame[:] = result


_cn_font = None

def _put_cn_text(img, text, x, y, color):
    global _cn_font
    try:
        if _cn_font is None:
            from PIL import ImageFont
            _cn_font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)
        from PIL import ImageDraw
        pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil)
        draw.text((x, y), text, font=_cn_font, fill=(color[2], color[1], color[0]))
        rgb = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
        img[:] = rgb
    except Exception:
        pass


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/video")
def video():
    resp = Response(gen_mjpeg(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route("/status")
def status():
    return Response(
        stream_with_context(_sse_gen()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


def _sse_gen():
    last_id = 0
    try:
        while True:
            with _result_lock:
                r = latest_result
                c = analysis_count
            with _history_lock:
                h = list(history[-200:])
            with _state_lock:
                sr_vllm = vllm_ready
                sr_progress = collection_progress
                sr_state = collection_state
                sr_started = monitor_start_time
            data = {
                "result": r,
                "count": c,
                "history": [{"t": x["t"], "v": x["v"]} for x in h],
                "server_time": time.time(),
                "vllm_ready": sr_vllm,
                "collection_progress": sr_progress,
                "collection_state": sr_state,
                "started_at": sr_started,
            }
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            time.sleep(0.5)
    except GeneratorExit:
        pass
    except Exception:
        pass


@app.route("/health")
def health():
    with _state_lock:
        ok = vllm_ready
        cs = collection_state
    return {"ok": ok, "vllm": ok, "camera": camera is not None,
            "state": cs, "count": analysis_count}


@app.route("/control", methods=["POST"])
def control():
    global analysis_count

    body = request.get_json(force=True)
    action = body.get("action")

    if action == "start":
        with _state_lock:
            cs = collection_state
        if cs not in ("idle", "done"):
            return {"ok": False, "error": f"current state: {cs}"}, 400
        t = threading.Thread(target=_run_collection_and_analyze, daemon=True)
        t.start()
        return {"ok": True, "state": "collecting"}

    if action == "reset":
        with _result_lock:
            global latest_result
            latest_result = None
            analysis_count = 0
        with _history_lock:
            history.clear()
        return {"ok": True, "message": "reset"}

    return {"ok": False, "error": f"unknown action: {action}"}, 400


def _crop_face_region(frame):
    h, w = frame.shape[:2]
    cx, cy, axes = _get_ellipse_params(w, h)
    rx, ry = axes

    x1 = max(0, cx - rx)
    y1 = max(0, cy - ry)
    x2 = min(w, cx + rx)
    y2 = min(h, cy + ry)

    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.ellipse(mask, (cx, cy), axes, 0, 0, 360, 255, -1)

    cropped = frame[y1:y2, x1:x2].copy()
    cmask = mask[y1:y2, x1:x2]

    cropped[cmask == 0] = 0

    resized = cv2.resize(cropped, (cfg.analysis_width, cfg.analysis_height),
                         interpolation=cv2.INTER_LINEAR)
    return resized


def _run_collection_and_analyze():
    global latest_result, analysis_count, collection_progress, collection_state, history

    with _state_lock:
        collection_state = "collecting"
        collection_progress = 0.0

    frames = []
    interval = 1.0 / cfg.collect_fps
    total_frames = int(cfg.collect_seconds * cfg.collect_fps)
    start_t = time.time()
    end_t = start_t + cfg.collect_seconds

    while time.time() < end_t:
        with _frame_lock:
            f = latest_frame.copy() if latest_frame is not None else None
        if f is not None:
            cropped = _crop_face_region(f)
            frames.append(cropped)
        elapsed = time.time() - start_t
        with _state_lock:
            collection_progress = min(round((elapsed / cfg.collect_seconds) * 100, 1), 99.0)
        time.sleep(interval)

    with _state_lock:
        collection_progress = 99.0

    if not frames:
        with _state_lock:
            collection_state = "idle"
            collection_progress = 0.0
        return

    with _state_lock:
        collection_state = "analyzing"

    print(f"[+] Analyzing {len(frames)} frames")
    result = analyzer.analyze_multi_frame(frames)
    elapsed = time.time() - start_t

    if result:
        guidance = generate_guidance(result)
        with _result_lock:
            latest_result = result
            latest_result["_guidance"] = guidance
            analysis_count += 1
            result["_analysis_id"] = analysis_count
            result["_elapsed"] = round(elapsed, 2)
            result["_frames"] = len(frames)
            result["_timestamp"] = time.strftime("%H:%M:%S")
        with _history_lock:
            d = result.get("overall_distress", 1)
            history.append({"t": time.time(), "v": d})
            if len(history) > cfg.max_history_size:
                history.pop(0)
        logger.log({
            "analysis": analysis_count,
            "elapsed": round(elapsed, 2),
            "frames": len(frames),
            "result": result,
        })
        print(f"[{analysis_count}] {len(frames)} frames, distress={d:.1f}/5 concern={result.get('concern_level', '?')}")
    else:
        print(f"[-] Multi-frame analysis failed (no result)")
        with _result_lock:
            latest_result = {
                "_error": True,
                "_error_message": "分析失败，模型返回结果异常，请重试",
                "overall_distress": 0,
                "concern_level": "low",
                "_analysis_id": analysis_count + 1,
                "_elapsed": round(elapsed, 2),
                "_frames": len(frames),
                "_timestamp": time.strftime("%H:%M:%S"),
            }

    with _state_lock:
        collection_state = "done"
        collection_progress = 100.0


def _cleanup(*args):
    print("\n[+] Shutting down ...")
    if logger:
        logger.close()
    if camera:
        camera.release()
    print("[+] Clean exit")
    sys.exit(0)


def main():
    global camera, monitor_start_time

    signal.signal(signal.SIGINT, _cleanup)
    signal.signal(signal.SIGTERM, _cleanup)

    print("[+] Initializing camera ...")
    camera = Camera(cfg.camera_index, cfg.camera_width, cfg.camera_height, cfg.camera_fps)
    camera.start()
    actual = camera.actual_resolution
    if actual != (cfg.camera_width, cfg.camera_height):
        print(f"[!] Camera resolution mismatch: requested {cfg.camera_width}x{cfg.camera_height}, got {actual[0]}x{actual[1]}")
    else:
        print(f"[+] Camera: index={cfg.camera_index} {actual[0]}x{actual[1]} @ {cfg.camera_fps}fps")

    with _state_lock:
        monitor_start_time = time.time()

    threading.Thread(target=capture_loop, daemon=True).start()
    threading.Thread(target=connect_vllm, daemon=True).start()

    print(f"[+] Web dashboard: http://127.0.0.1:{cfg.web_port}")
    print("[+] Mode: manual capture-then-analyze (click '开始监测')")
    print("[+] Press Ctrl+C to stop")
    app.run(host=cfg.web_host, port=cfg.web_port, debug=cfg.web_debug,
            threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
