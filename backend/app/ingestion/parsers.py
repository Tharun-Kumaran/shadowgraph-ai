"""Parsers for supported input formats.

Every parser returns ``(records, rejected, fmt)`` where ``records`` is a list
of ``(index, dict)`` raw records. Parsing is pure: nothing is executed and
no filesystem paths from the input are ever opened.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import PurePath
from typing import Any

from app.schemas.observations import RejectedRecord

SUPPORTED_EXTENSIONS = {".json": "json", ".jsonl": "jsonl", ".ndjson": "jsonl", ".csv": "csv", ".txt": "text"}

csv.field_size_limit(1_000_000)


class IngestionError(ValueError):
    """The whole upload is unacceptable (format, size, encoding)."""


def safe_filename(name: str | None) -> str:
    """Reduce an uploaded filename to a bare, display-only basename."""
    if not name:
        return "upload"
    base = PurePath(name.replace("\\", "/")).name
    cleaned = "".join(c for c in base if c.isalnum() or c in "._- ")[:128].strip(" .")
    return cleaned or "upload"


def detect_format(filename: str, declared: str | None = None) -> str:
    if declared:
        if declared not in {"json", "jsonl", "csv", "text", "stix"}:
            raise IngestionError(f"unsupported format '{declared}'")
        return declared
    suffix = PurePath(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise IngestionError(f"unsupported file extension '{suffix}'; use .json, .jsonl, .csv or .txt")
    return SUPPORTED_EXTENSIONS[suffix]


def decode_bytes(data: bytes) -> str:
    if b"\x00" in data[:8192]:
        raise IngestionError("binary content detected (NUL bytes); only UTF-8 text is accepted")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise IngestionError(f"file is not valid UTF-8 (byte offset {exc.start})") from exc


def _is_stix_bundle(obj: Any) -> bool:
    return isinstance(obj, dict) and obj.get("type") == "bundle" and isinstance(obj.get("objects"), list)


def parse_stix(bundle: dict) -> tuple[list[tuple[int, dict]], list[RejectedRecord]]:
    """Map STIX 2.x objects with analyst-readable text to observations."""
    records, rejected = [], []
    bundle_id = str(bundle.get("id", "stix-bundle"))
    for i, obj in enumerate(bundle["objects"]):
        if not isinstance(obj, dict) or "type" not in obj:
            rejected.append(RejectedRecord(index=i, reason="STIX object without type"))
            continue
        otype = obj["type"]
        parts: list[str] = []
        if otype == "indicator":
            parts = [obj.get("name", ""), obj.get("description", ""), obj.get("pattern", "")]
        elif otype in {"report", "note", "malware", "vulnerability", "threat-actor", "campaign", "intrusion-set"}:
            parts = [obj.get("name", ""), obj.get("abstract", ""), obj.get("description", ""), obj.get("content", "")]
        else:
            continue  # relationship, identity, marking-definition, SCOs: no free text
        text = "\n".join(p for p in parts if isinstance(p, str) and p.strip())
        if not text:
            rejected.append(RejectedRecord(index=i, reason=f"STIX {otype} has no textual content"))
            continue
        records.append((i, {
            "id": obj.get("id"),
            "text": text,
            "timestamp": obj.get("valid_from") or obj.get("published") or obj.get("created"),
            "source": f"stix:{bundle_id}",
            "source_type": "stix",
            "stix_type": otype,
        }))
    return records, rejected


def parse_content(text: str, fmt: str) -> tuple[list[tuple[int, dict]], list[RejectedRecord], str]:
    rejected: list[RejectedRecord] = []
    if fmt in {"json", "stix"}:
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as exc:
            raise IngestionError(f"invalid JSON at line {exc.lineno}: {exc.msg}") from exc
        if _is_stix_bundle(obj):
            recs, rej = parse_stix(obj)
            return recs, rej, "stix"
        if fmt == "stix":
            raise IngestionError("expected a STIX 2.x bundle (type=bundle)")
        if isinstance(obj, dict) and isinstance(obj.get("records"), list):
            obj = obj["records"]
        if not isinstance(obj, list):
            raise IngestionError("JSON must be an array of records, {\"records\": [...]}, or a STIX bundle")
        recs = []
        for i, item in enumerate(obj):
            if isinstance(item, dict):
                recs.append((i, item))
            else:
                rejected.append(RejectedRecord(index=i, reason="record is not a JSON object"))
        return recs, rejected, "json"

    if fmt == "jsonl":
        recs = []
        for i, line in enumerate(text.splitlines()):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                rejected.append(RejectedRecord(index=i, reason=f"invalid JSON: {exc.msg}"))
                continue
            if isinstance(item, dict):
                recs.append((i, item))
            else:
                rejected.append(RejectedRecord(index=i, reason="line is not a JSON object"))
        return recs, rejected, "jsonl"

    if fmt == "csv":
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise IngestionError("CSV has no header row")
        recs = []
        try:
            for i, row in enumerate(reader):
                if None in row:
                    rejected.append(RejectedRecord(index=i, reason="row has more fields than header"))
                    continue
                recs.append((i, {k.strip().lower(): v for k, v in row.items() if k}))
        except csv.Error as exc:
            raise IngestionError(f"malformed CSV: {exc}") from exc
        return recs, rejected, "csv"

    if fmt == "text":
        # Blank-line separated paragraphs become individual observations.
        blocks = [b.strip() for b in text.replace("\r\n", "\n").split("\n\n")]
        return [(i, {"text": b}) for i, b in enumerate(blocks) if b], rejected, "text"

    raise IngestionError(f"unsupported format '{fmt}'")
