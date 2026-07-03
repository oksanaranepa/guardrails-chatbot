"""Структурированное логирование сессий в JSONL."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class SessionLogger:
    """Пишет события каждого этапа пайплайна в logs/sessions.jsonl."""

    def __init__(self, log_dir: str | Path | None = None):
        root = Path(__file__).resolve().parents[2]
        self.log_dir = Path(log_dir) if log_dir else root / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "sessions.jsonl"

    def new_session_id(self) -> str:
        return str(uuid.uuid4())[:8]

    def log_event(self, session_id: str, event: str, payload: dict[str, Any] | None = None) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "event": event,
            "payload": payload or {},
        }
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def read_session(self, session_id: str) -> list[dict[str, Any]]:
        if not self.log_file.exists():
            return []
        events = []
        with self.log_file.open(encoding="utf-8") as f:
            for line in f:
                record = json.loads(line)
                if record.get("session_id") == session_id:
                    events.append(record)
        return events
