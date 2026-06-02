# -*- coding: utf-8 -*-

import base64
import json
import os
from typing import Optional, Dict, Any

import cv2
import numpy as np
from openai import OpenAI

from config import Config
from prompts import SYSTEM_PROMPT, ANALYSIS_PROMPT, MULTI_FRAME_PROMPT


class Analyzer:
    def __init__(self, config: Config):
        self._config = config
        self._client = OpenAI(
            api_key=config.vllm_api_key,
            base_url=config.vllm_api_url,
        )
        self._analysis_width = config.analysis_width
        self._analysis_height = config.analysis_height
        self._log_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "logs", "analyzer.log"
        )

    def _log(self, msg):
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(f"{msg}\n")

    def _frame_to_base64(self, frame: np.ndarray) -> str:
        h, w = frame.shape[:2]
        if w != self._analysis_width or h != self._analysis_height:
            frame = cv2.resize(frame, (self._analysis_width, self._analysis_height),
                               interpolation=cv2.INTER_AREA)
        _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        return base64.b64encode(buffer).decode("utf-8")

    def analyze(self, frame: np.ndarray) -> Optional[Dict[str, Any]]:
        b64 = self._frame_to_base64(frame)
        data_url = f"data:image/jpeg;base64,{b64}"

        try:
            resp = self._client.chat.completions.create(
                model=self._config.model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": ANALYSIS_PROMPT},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    },
                ],
                max_tokens=self._config.max_tokens,
                temperature=self._config.temperature,
                top_p=self._config.top_p,
            )
            raw = resp.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.strip("`").strip()
                if raw.lower().startswith("json"):
                    raw = raw[4:].strip()
            return json.loads(raw)
        except json.JSONDecodeError as e:
            self._log(f"[analyzer] JSON decode error in analyze(): {e}")
            self._log(f"[analyzer] raw: {raw[:500]}")
            return None
        except Exception as e:
            self._log(f"[analyzer] Exception in analyze(): {type(e).__name__}: {e}")
            return None

    def analyze_multi_frame(
        self,
        frames: list[np.ndarray],
    ) -> Optional[Dict[str, Any]]:
        content = [{"type": "text", "text": MULTI_FRAME_PROMPT}]
        # Sample frames to avoid context overflow
        max_frames = 24
        sampled = frames
        if len(frames) > max_frames:
            indices = {0, len(frames) - 1}
            remaining = max_frames - len(indices)
            step = len(frames) / (remaining + 1)
            for i in range(1, remaining + 1):
                indices.add(int(i * step))
            indices = sorted(indices)[:max_frames]
            sampled = [frames[i] for i in indices]
            self._log(f"[analyzer] sampled {len(sampled)}/{len(frames)} frames (first+last preserved)")
        for frame in sampled:
            b64 = self._frame_to_base64(frame)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            })

        try:
            resp = self._client.chat.completions.create(
                model=self._config.model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": content},
                ],
                max_tokens=self._config.max_tokens,
                temperature=self._config.temperature,
                top_p=self._config.top_p,
            )
            raw = resp.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.strip("`").strip()
                if raw.lower().startswith("json"):
                    raw = raw[4:].strip()
            return json.loads(raw)
        except json.JSONDecodeError as e:
            self._log(f"[analyzer] JSON error: {e}")
            self._log(f"[analyzer] raw: {raw[:500]}")
            return None
        except Exception as e:
            self._log(f"[analyzer] Exception: {type(e).__name__}: {e}")
            return None

    def check_health(self) -> bool:
        try:
            self._client.models.list()
            return True
        except Exception:
            return False
