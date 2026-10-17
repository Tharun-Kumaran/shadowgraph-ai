"""Normalise raw records into validated ``Observation`` objects.

Source text is treated strictly as untrusted data: it is hashed, extracted
and stored, never interpreted as instructions.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.security import strip_control_chars
from app.extraction.extractor import ExtractionPipeline, default_pipeline
from app.schemas.observations import Observation

_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_HANDLE_RE = re.compile(r"^[\w.\-@ ]{1,64}$", re.UNICODE)
_SLUG_RE = re.compile(r"[^a-z0-9._-]+")

FIELD_ALIASES = {
    "id": ("observation_id", "post_id", "id", "uuid"),
    "author": ("author_handle", "handle", "author", "user", "username"),
    "text": ("text", "content", "body", "message", "description"),
    "timestamp": ("observed_at", "timestamp", "created_at", "date", "time"),
    "source": ("source_id", "source", "forum", "feed"),
    "source_name": ("source_name",),
    "source_url": ("source_url", "url", "link"),
    "source_type": ("source_type",),
    "language": ("language", "lang"),
    "synthetic": ("synthetic",),
}


class RecordError(ValueError):
    pass


def _get(record: dict[str, Any], key: str) -> Any:
    for alias in FIELD_ALIASES[key]:
        if alias in record and record[alias] not in (None, ""):
            return record[alias]
    return None


def content_hash(text: str) -> str:
    norm = " ".join(unicodedata.normalize("NFC", text).split())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def slugify(value: str) -> str:
    return _SLUG_RE.sub("-", value.strip().lower()).strip("-")[:80] or "unknown"


def parse_timestamp(value: Any) -> tuple[datetime | None, list[str]]:
    notes: list[str] = []
    if value is None or value == "":
        return None, notes
    try:
        if isinstance(value, (int, float)) or (isinstance(value, str) and value.strip().isdigit()):
            num = float(value)
            if num > 1e12:  # milliseconds
                num /= 1000.0
            dt = datetime.fromtimestamp(num, tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except (ValueError, OverflowError, OSError):
        raise RecordError(f"unparseable timestamp: {str(value)[:40]!r}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
        notes.append("timestamp had no timezone; assumed UTC")
    dt = dt.astimezone(timezone.utc)
    if dt > datetime.now(timezone.utc) + timedelta(days=1):
        notes.append("timestamp is in the future")
    return dt, notes


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def normalize_record(
    record: dict[str, Any],
    *,
    default_source: str,
    default_source_type: str,
    max_text_chars: int,
    retention: str = "full",
    truncated_chars: int = 500,
    pipeline: ExtractionPipeline | None = None,
    collected_at: datetime | None = None,
    force_synthetic: bool = False,
) -> Observation:
    raw_text = _get(record, "text")
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise RecordError("missing or empty text")
    text = strip_control_chars(unicodedata.normalize("NFC", raw_text)).strip()
    if len(text) > max_text_chars:
        raise RecordError(f"text exceeds {max_text_chars} characters")

    errors: list[str] = []
    observed_at, ts_notes = parse_timestamp(_get(record, "timestamp"))
    errors.extend(ts_notes)

    author = _get(record, "author")
    if author is not None:
        author = strip_control_chars(str(author)).strip().lstrip("@")
        if not _HANDLE_RE.match(author):
            raise RecordError("invalid author handle (1-64 letters, digits, space, . _ - @)")

    source_raw = str(_get(record, "source") or default_source)
    source_id = slugify(source_raw)
    source_name = str(_get(record, "source_name") or source_raw)[:120]
    source_type = str(_get(record, "source_type") or default_source_type)
    if source_type not in {"file", "feed", "tor", "synthetic", "stix", "manual"}:
        source_type = default_source_type
    source_url = _get(record, "source_url")
    if source_url is not None:
        source_url = str(source_url)[:2048]
        if not re.match(r"^(https?|urn|stix):", source_url, re.IGNORECASE):
            errors.append("source_url dropped: unsupported scheme")
            source_url = None

    chash = content_hash(text)
    rid = _get(record, "id")
    if rid is not None:
        rid = str(rid).strip()
        if not _ID_RE.match(rid):
            raise RecordError("invalid id (1-128 chars of letters, digits, . _ : -)")
        obs_id = rid
    else:
        obs_id = "obs-" + hashlib.sha256(f"{source_id}|{chash}".encode()).hexdigest()[:20]

    extraction = (pipeline or default_pipeline()).run(text)
    synthetic = force_synthetic or _as_bool(_get(record, "synthetic") or False)

    if retention == "full":
        kept: str | None = text
    elif retention == "truncated":
        kept = text[:truncated_chars]
    else:
        kept = None

    lang = _get(record, "language")
    return Observation(
        observation_id=obs_id,
        source_id=source_id,
        source_name=source_name,
        source_type=source_type,  # type: ignore[arg-type]
        source_url=source_url,
        collected_at=collected_at or datetime.now(timezone.utc),
        observed_at=observed_at,
        author_handle=author,
        text=kept,
        text_retention=retention,  # type: ignore[arg-type]
        text_length=len(text),
        content_hash=chash,
        language=str(lang)[:16] if lang else None,
        synthetic=synthetic,
        entities=[e.to_dict() for e in extraction.entities],
        status="extracted",
        errors=errors,
    )
