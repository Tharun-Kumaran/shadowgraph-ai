"""Optional, isolated Tor collector (improved ``safe_fetch_onion``).

Disabled unless ``SHADOWGRAPH_TOR_ENABLED=true``. It fetches exactly one
explicitly supplied, *authorised* v3 onion URL through a SOCKS5 proxy with
proxy-side DNS resolution (``socks5h``). It never crawls, follows links or
redirects, or executes content. Requires ``PySocks``.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

import requests

from app.ingestion.collectors import CollectionError, FetchResult, hardened_fetch

ONION_V3 = re.compile(r"^[a-z2-7]{56}\.onion$")


def safe_fetch_onion(
    url: str,
    *,
    proxy: str = "socks5h://127.0.0.1:9050",
    timeout: tuple[float, float] = (15.0, 45.0),
    max_bytes: int = 2 * 1024 * 1024,
    session: requests.Session | None = None,
) -> FetchResult:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme not in {"http", "https"} or not ONION_V3.match(host):
        raise CollectionError("only explicit v3 .onion http(s) URLs are accepted")
    if not proxy.startswith("socks5h://"):
        # socks5:// would resolve DNS locally and leak the lookup.
        raise CollectionError("proxy must use socks5h:// (proxy-side DNS resolution)")
    proxies = {"http": proxy, "https": proxy}
    own_session = session is None
    session = session or requests.Session()
    try:
        result = hardened_fetch(
            session,
            url,
            allowed_schemes=frozenset({"http", "https"}),
            timeout=timeout,
            max_bytes=max_bytes,
            proxies=proxies,
            allowed_content_types=frozenset({"text/html", "text/plain"}),
        )
        result.metadata.update({"via": "tor", "host": host})
        return result
    finally:
        if own_session:
            session.close()
