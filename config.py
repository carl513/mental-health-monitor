# -*- coding: utf-8 -*-

import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class Config:
    # vLLM server
    vllm_api_url: str = "http://192.168.0.190:18004/v1"
    vllm_api_key: str = "EMPTY"
    model_name: str = "Qwen/Qwen3-VL-8B-Instruct"
    # NOTE: model_name is passed as the `model` param in the API call.
    # vLLM typically ignores this; change it if your server expects a specific name.
    # For local vLLM with downloaded models, use the HF model ID or local path as loaded.

    # Camera
    camera_index: int = 0
    camera_width: int = 1280
    camera_height: int = 720
    stream_width: int = 1280
    stream_height: int = 720
    camera_fps: int = 10
    analysis_width: int = 768
    analysis_height: int = 576

    # Analysis
    analysis_interval_seconds: float = 10.0
    max_history_size: int = 300

    # Capture-then-analyze mode
    collect_seconds: float = 15.0
    collect_fps: int = 5       # frames per second during collection

    # Alert thresholds (1-5 scale)
    warning_threshold: float = 3.0
    critical_threshold: float = 4.0

    # Response diversity - collect this many frames before each analysis
    frames_per_analysis: int = 1

    log_dir: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

    # Generation params
    max_tokens: int = 4096
    temperature: float = 0.1
    top_p: float = 0.9

    # Web dashboard
    web_host: str = "0.0.0.0"
    web_port: int = 5000
    web_debug: bool = False

    enabled_dimensions: List[str] = field(default_factory=lambda: [
        "stress", "fatigue", "anxiety", "sadness", "focus", "posture_tension",
        "irritation", "depression", "emotional_stability", "eye_contact",
        "sleep_deficit_signs", "psychomotor_retardation", "positive_affect_blunting",
    ])
