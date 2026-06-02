# -*- coding: utf-8 -*-

import cv2
import numpy as np
import time
from threading import Lock, Thread
from typing import Optional


class Camera:
    def __init__(self, index: int = 0, width: int = 640, height: int = 480, fps: int = 30):
        self._index = index
        self._width = width
        self._height = height
        self._fps = fps
        self._cap: Optional[cv2.VideoCapture] = None
        self._lock = Lock()
        self._running = False
        self._last_frame: Optional[np.ndarray] = None
        self._frame_count = 0
        self._thread: Optional[Thread] = None

    def start(self):
        with self._lock:
            if self._running:
                return
            self._cap = cv2.VideoCapture(self._index)
            if not self._cap.isOpened():
                raise RuntimeError(f"Cannot open camera index {self._index}")
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
            self._cap.set(cv2.CAP_PROP_FPS, self._fps)
            self._running = True
        self._thread = Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def _capture_loop(self):
        while self._running:
            with self._lock:
                if self._cap is None:
                    break
                ret, frame = self._cap.read()
                if ret:
                    self._last_frame = frame
                    self._frame_count += 1
            time.sleep(1.0 / self._fps)

    def read(self) -> Optional[np.ndarray]:
        with self._lock:
            if self._last_frame is None:
                return None
            return self._last_frame.copy()

    @property
    def actual_resolution(self):
        with self._lock:
            if self._cap is None:
                return (0, 0)
            w = self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            h = self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            return (int(w), int(h))

    @property
    def frame_count(self) -> int:
        with self._lock:
            return self._frame_count

    def release(self):
        with self._lock:
            self._running = False
            if self._cap:
                self._cap.release()
                self._cap = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.release()
