# -*- coding: utf-8 -*-

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional


class SessionLogger:
    def __init__(self, log_dir: str):
        self._log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._file_path = os.path.join(log_dir, f"session_{timestamp}.jsonl")
        self._file = open(self._file_path, "w", encoding="utf-8")

    def log(self, entry: Dict[str, Any]):
        entry["timestamp"] = datetime.now().isoformat()
        self._file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._file.flush()

    def close(self):
        if self._file and not self._file.closed:
            self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
