"""Structured JSON logging with secret redaction."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone

_SECRET_PATTERNS = [
    re.compile(r"(?i)(password|api[_-]?key|secret|token)(\"?\s*[:=]\s*\"?)([^\s\",]+)"),
    re.compile(r"(?i)(bolt|neo4j|http|https)://[^:/\s]+:[^@/\s]+@"),
]


def redact(message: str) -> str:
    message = _SECRET_PATTERNS[0].sub(lambda m: f"{m.group(1)}{m.group(2)}***", message)
    message = _SECRET_PATTERNS[1].sub(lambda m: f"{m.group(1)}://***:***@", message)
    return message


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": redact(record.getMessage()),
        }
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update({k: redact(str(v)) for k, v in extra.items()})
        if record.exc_info:
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level.upper())
    # The neo4j driver is verbose at INFO.
    logging.getLogger("neo4j").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
