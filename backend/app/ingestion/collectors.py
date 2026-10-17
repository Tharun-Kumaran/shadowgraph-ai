"""Collectors for remote sources.

``HttpFeedCollector`` fetches only feeds allow-listed in configuration.
``safe_fetch_onion`` (in tor_collector) is an optional, isolated adapter.
Both share the same hardened streaming fetch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol
from urllib.parse import urlsplit

import requests

ALLOWED_CONTENT_TYPES = frozenset(
    {"text/plain", "text/html", "text/csv", "application/json", "application/x-ndjson", "application/stix+json"}
)


class CollectionError(RuntimeError):
    pass


@dataclass
class FetchResult:
    url: str
    status_code: int
    content_type: str
    body: bytes
    fetched_at: datetime
    metadata: dict = field(default_factory=dict)


class Collector(Protocol):
    name: str

    def collect(self) -> FetchResult: ...


def hardened_fetch(
    session: requests.Session,
    url: str,
    *,
    allowed_schemes: frozenset[str] = frozenset({"https"}),
    timeout: tuple[float, float] = (10.0, 30.0),
    max_bytes: int = 5 * 1024 * 1024,
    proxies: dict[str, str] | None = None,
    allowed_content_types: frozenset[str] = ALLOWED_CONTENT_TYPES,
) -> FetchResult:
    """Stream a single URL with strict limits. Never executes content.

    * scheme allow-list, no redirects (3xx is an error)
    * connect/read timeouts
    * content-type allow-list
    * hard response-size cap enforced while streaming
    * TLS verification left at the library default (enabled)
    """
    parts = urlsplit(url)
    if parts.scheme.lower() not in allowed_schemes or not parts.hostname:
        raise CollectionError(f"unsupported URL scheme or host: {parts.scheme!r}")
    try:
        resp = session.get(url, timeout=timeout, stream=True, allow_redirects=False, proxies=proxies)
    except requests.RequestException as exc:
        raise CollectionError(f"request failed: {type(exc).__name__}") from exc
    with resp:
        if 300 <= resp.status_code < 400:
            raise CollectionError(f"redirect refused (HTTP {resp.status_code})")
        if resp.status_code != 200:
            raise CollectionError(f"unexpected HTTP status {resp.status_code}")
        ctype = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if ctype not in allowed_content_types:
            raise CollectionError(f"content type not allowed: {ctype or 'missing'}")
        declared = resp.headers.get("Content-Length")
        if declared and declared.isdigit() and int(declared) > max_bytes:
            raise CollectionError(f"declared size {declared} exceeds limit {max_bytes}")
        buf = bytearray()
        try:
            for chunk in resp.iter_content(chunk_size=16384):
                buf.extend(chunk)
                if len(buf) > max_bytes:
                    raise CollectionError(f"response exceeded {max_bytes} bytes")
        except requests.RequestException as exc:
            raise CollectionError(f"read failed: {type(exc).__name__}") from exc
        return FetchResult(
            url=url,
            status_code=resp.status_code,
            content_type=ctype,
            body=bytes(buf),
            fetched_at=datetime.now(timezone.utc),
            metadata={"bytes": len(buf)},
        )


class HttpFeedCollector:
    """Collect a configured, authorised public feed (HTTPS only)."""

    def __init__(self, feed_id: str, url: str, timeout_s: float = 15.0, max_bytes: int = 5 * 1024 * 1024,
                 session: requests.Session | None = None):
        self.name = f"feed:{feed_id}"
        self.feed_id = feed_id
        self.url = url
        self.timeout = (min(10.0, timeout_s), timeout_s)
        self.max_bytes = max_bytes
        self.session = session or requests.Session()

    def collect(self) -> FetchResult:
        return hardened_fetch(self.session, self.url, timeout=self.timeout, max_bytes=self.max_bytes)
