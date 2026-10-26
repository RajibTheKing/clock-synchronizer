"""Per-run JSONL logging of NTP sync results, one file per NTP server."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

from app.data.models import NtpSyncResult

DEFAULT_BASE_DIR = Path(__file__).resolve().parents[2]


class SyncResultLogger:
    """Creates a timestamped run folder and appends one JSON line per result."""

    def __init__(self, servers: Iterable[str], base_dir: Path = DEFAULT_BASE_DIR) -> None:
        self.run_dir = base_dir / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir.mkdir(parents=True, exist_ok=True)
        for server in servers:
            self._path_for(server).touch()

    def _path_for(self, server: str) -> Path:
        return self.run_dir / f"{server}.jsonl"

    def log(self, server: str, result: NtpSyncResult) -> None:
        with self._path_for(server).open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(result)) + "\n")
