"""Bounded, text-only Tor hidden-service crawler.

Design is informed by the established open-source dark-web OSINT tools:

* **TorBot** (DedSecInside): breadth-first crawl, link harvesting, liveness
  tracking of onion services, relationship (site -> site) mapping.
* **OnionScan** (s-rah): correlation artifacts (PGP, wallets, ...) used to tie
  separate hidden services together -- handled downstream by the extractor.
* **Robin** (apurvsinghgautam): seed *discovery* through onion search engines,
  then scrape + LLM analysis -- discovery lives in :func:`discover_onions`.

Guard-rails (this is a defensive CTI collector, not a general spider):

* onion v3 hosts only -- it can never leave Tor or touch clearnet / SSRF space;
* hard caps on depth, pages, pages per host and wall-clock time;
* per-host politeness delay with jitter, ``robots.txt`` honoured;
* text/html + text/plain only, size-capped, no redirects, nothing executed,
  no images/media/archives are ever requested or stored;
* fixed Tor-Browser user-agent (blend in, do not fingerprint) -- no logins,
  captcha solving or auth bypass;
* a content safety filter drops (never stores, never follows) pages that match
  child-exploitation indicators and blocks the whole host.

The crawler is transport-agnostic: it takes a ``fetch(url) -> FetchResult``
callable, so it is unit-testable without a Tor daemon.
"""

from __future__ import annotations

import hashlib
import html as html_lib
import random
import re
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Callable, Iterable
from urllib import robotparser
from urllib.parse import unquote, urldefrag, urljoin, urlsplit

import requests

from app.ingestion.collectors import CollectionError, FetchResult
from app.ingestion.tor_collector import ONION_V3, safe_fetch_onion

# Tor Browser's (ESR-based) user-agent: identical across all Tor Browser users,
# which is the correct OpSec posture -- randomising makes you *more* unique.
TOR_BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; rv:128.0) Gecko/20100101 Firefox/128.0"

# Ahmia indexes onion services and filters abusive content.
DEFAULT_SEARCH_ENGINES = (
    "http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/search/?q={q}",
)

_ONION_RE = re.compile(r"(?:https?://)?([a-z2-7]{56}\.onion)(?::\d+)?(/[^\s\"'<>)]*)?", re.I)
_MEDIA_EXT = re.compile(
    r"\.(?:jpe?g|png|gif|webp|bmp|ico|svg|mp[34]|avi|mkv|mov|webm|zip|rar|7z|tar|gz|bz2|"
    r"iso|exe|apk|dmg|pdf|docx?|xlsx?|pptx?|torrent|wav|flac|ogg)(?:\?|$)",
    re.I,
)
# Content safety filter. Matching pages are discarded, never stored or followed.
_UNSAFE_RE = re.compile(
    r"\b(?:child\s*porn\w*|\bcp\s+links?\b|pedo\w*|jail\s*bait|preteen\s*(?:porn|sex|nude)\w*|"
    r"lolita\s*(?:porn|sex|nude)\w*|csam)\b",
    re.I,
)
_SKIP_TAGS = {"script", "style", "noscript", "template", "svg"}


def canonicalize(url: str) -> str | None:
    """Normalise an onion URL; return None if it is not a crawlable v3 onion URL."""
    try:
        url, _ = urldefrag(url.strip())
        parts = urlsplit(url)
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    if parts.scheme.lower() not in {"http", "https"} or not ONION_V3.match(host):
        return None
    if _MEDIA_EXT.search(parts.path or ""):
        return None
    path = parts.path or "/"
    query = f"?{parts.query}" if parts.query else ""
    return f"{parts.scheme.lower()}://{host}{path}{query}"


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.hrefs: list[str] = []
        self._in_title = False
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append(href)
        elif tag in {"br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "pre"}:
            self.text_parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title_parts.append(data)
        elif not self._skip:
            self.text_parts.append(data)


def parse_html(body: str) -> tuple[str, str, list[str]]:
    """Return (title, clean_text, raw_hrefs)."""
    p = _PageParser()
    try:
        p.feed(body)
        p.close()
    except Exception:  # malformed markup must never kill the crawl
        pass
    title = re.sub(r"\s+", " ", "".join(p.title_parts)).strip()[:200]
    text = re.sub(r"[ \t\r\f\v]+", " ", "".join(p.text_parts))
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    return title, text, p.hrefs


def is_unsafe(title: str, text: str) -> bool:
    return bool(_UNSAFE_RE.search(f"{title}\n{text}"))


@dataclass
class CrawlConfig:
    max_depth: int = 2
    max_pages: int = 25
    max_pages_per_host: int = 15
    delay_s: float = 2.0
    jitter_s: float = 1.5
    time_budget_s: float = 240.0
    respect_robots: bool = True
    follow_external_onions: bool = True
    max_text_chars: int = 15000

    def clamp(self, *, pages_cap: int = 100, depth_cap: int = 4, time_cap: float = 600.0) -> "CrawlConfig":
        self.max_pages = max(1, min(self.max_pages, pages_cap))
        self.max_depth = max(0, min(self.max_depth, depth_cap))
        self.max_pages_per_host = max(1, min(self.max_pages_per_host, self.max_pages))
        self.time_budget_s = max(5.0, min(self.time_budget_s, time_cap))
        self.delay_s = max(0.0, self.delay_s)
        return self


@dataclass
class PageRecord:
    url: str
    host: str
    depth: int
    title: str
    text: str
    content_hash: str
    fetched_at: datetime
    out_links: int


@dataclass
class CrawlResult:
    seeds: list[str]
    pages: list[PageRecord] = field(default_factory=list)
    # host -> "alive" | "dead" | "blocked" | "robots_denied"
    host_status: dict[str, str] = field(default_factory=dict)
    edges: set[tuple[str, str]] = field(default_factory=set)  # (src_host, dst_host)
    errors: list[dict] = field(default_factory=list)
    skipped_duplicates: int = 0
    blocked_pages: int = 0
    stopped_reason: str = "queue_exhausted"
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None

    def summary(self) -> dict:
        return {
            "seeds": self.seeds,
            "pages_collected": len(self.pages),
            "hosts": dict(self.host_status),
            "links_discovered": len(self.edges),
            "duplicates_skipped": self.skipped_duplicates,
            "blocked_by_safety_filter": self.blocked_pages,
            "errors": self.errors[:25],
            "stopped_reason": self.stopped_reason,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


class OnionCrawler:
    def __init__(
        self,
        fetch: Callable[[str], FetchResult],
        config: CrawlConfig | None = None,
        *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        rng: random.Random | None = None,
    ) -> None:
        self.fetch = fetch
        self.cfg = config or CrawlConfig()
        self._sleep = sleep
        self._clock = clock
        self._rng = rng or random.Random()
        self._robots: dict[str, robotparser.RobotFileParser | None] = {}
        self._last_hit: dict[str, float] = {}

    # -- politeness ------------------------------------------------------
    def _polite_wait(self, host: str) -> None:
        last = self._last_hit.get(host)
        if last is not None:
            wait = self.cfg.delay_s + self._rng.uniform(0, self.cfg.jitter_s) - (self._clock() - last)
            if wait > 0:
                self._sleep(wait)
        self._last_hit[host] = self._clock()

    def _robots_allows(self, url: str, host: str) -> bool:
        if not self.cfg.respect_robots:
            return True
        if host not in self._robots:
            rp: robotparser.RobotFileParser | None = robotparser.RobotFileParser()
            try:
                self._polite_wait(host)
                res = self.fetch(f"{urlsplit(url).scheme}://{host}/robots.txt")
                rp.parse(res.body.decode("utf-8", "replace").splitlines())  # type: ignore[union-attr]
            except Exception:
                rp = None  # no/unfetchable robots.txt => allowed (standard behaviour)
            self._robots[host] = rp
        rp = self._robots[host]
        return True if rp is None else rp.can_fetch(TOR_BROWSER_UA, url)

    # -- main loop -------------------------------------------------------
    def run(self, seeds: Iterable[str]) -> CrawlResult:
        seed_list = [c for c in (canonicalize(s) for s in seeds) if c]
        res = CrawlResult(seeds=seed_list)
        queue: deque[tuple[str, int]] = deque((s, 0) for s in dict.fromkeys(seed_list))
        seen_urls: set[str] = set(u for u, _ in queue)
        seen_hashes: set[str] = set()
        per_host: dict[str, int] = {}
        deadline = self._clock() + self.cfg.time_budget_s

        while queue:
            if len(res.pages) >= self.cfg.max_pages:
                res.stopped_reason = "max_pages"
                break
            if self._clock() >= deadline:
                res.stopped_reason = "time_budget"
                break
            url, depth = queue.popleft()
            host = urlsplit(url).hostname or ""
            if res.host_status.get(host) in {"blocked", "dead"} and per_host.get(host, 0) == 0:
                continue
            if res.host_status.get(host) == "blocked":
                continue
            if per_host.get(host, 0) >= self.cfg.max_pages_per_host:
                continue
            if not self._robots_allows(url, host):
                res.host_status.setdefault(host, "robots_denied")
                continue

            self._polite_wait(host)
            try:
                fr = self.fetch(url)
            except CollectionError as exc:
                res.errors.append({"url": url, "error": str(exc)})
                if per_host.get(host, 0) == 0 and host not in res.host_status:
                    res.host_status[host] = "dead"
                continue
            except Exception as exc:  # never let one bad page abort the crawl
                res.errors.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
                continue

            per_host[host] = per_host.get(host, 0) + 1
            res.host_status[host] = "alive"
            body = fr.body.decode("utf-8", "replace")
            if fr.content_type == "text/plain":
                title, text, hrefs = "", body, []
            else:
                title, text, hrefs = parse_html(body)

            if is_unsafe(title, text):
                res.blocked_pages += 1
                res.host_status[host] = "blocked"
                continue  # discard: no storage, no link following

            text = text[: self.cfg.max_text_chars]
            chash = hashlib.sha256(text.encode()).hexdigest()
            if not text or chash in seen_hashes:
                res.skipped_duplicates += 1
                continue
            seen_hashes.add(chash)

            # Harvest links (anchors + bare onion URLs found in text, TorBot-style).
            candidates: list[str] = []
            for h in hrefs:
                candidates.append(urljoin(url, html_lib.unescape(h)))
            for m in _ONION_RE.finditer(unquote(body)):
                candidates.append(f"http://{m.group(1).lower()}{m.group(2) or '/'}")
            out = 0
            for cand in candidates:
                c = canonicalize(cand)
                if not c:
                    continue
                dst = urlsplit(c).hostname or ""
                if dst != host:
                    res.edges.add((host, dst))
                    if not self.cfg.follow_external_onions:
                        continue
                if c in seen_urls or depth + 1 > self.cfg.max_depth:
                    continue
                seen_urls.add(c)
                queue.append((c, depth + 1))
                out += 1

            res.pages.append(PageRecord(
                url=url, host=host, depth=depth, title=title, text=text,
                content_hash=chash, fetched_at=fr.fetched_at, out_links=out,
            ))

        res.finished_at = datetime.now(timezone.utc)
        return res


def make_tor_fetcher(
    proxy: str,
    *,
    timeout: tuple[float, float] = (20.0, 60.0),
    max_bytes: int = 1024 * 1024,
) -> Callable[[str], FetchResult]:
    """Fetcher that routes every request through Tor (socks5h, proxy-side DNS)."""
    session = requests.Session()
    session.headers.update({"User-Agent": TOR_BROWSER_UA, "Accept-Language": "en-US,en;q=0.5"})

    def _fetch(url: str) -> FetchResult:
        return safe_fetch_onion(
            url, proxy=proxy, timeout=timeout, max_bytes=max_bytes, session=session,
            follow_onion_redirects=True,
        )

    return _fetch


def discover_onions(
    fetch: Callable[[str], FetchResult],
    query: str,
    engines: Iterable[str] = DEFAULT_SEARCH_ENGINES,
    limit: int = 20,
    errors: list[str] | None = None,
) -> list[str]:
    """Robin-style discovery: query onion search engines and harvest onion hosts.

    Many engines (e.g. Ahmia) embed a rotating hidden token in the search form,
    so we load the engine home page first and replay its hidden inputs.
    """
    from urllib.parse import quote_plus

    found: dict[str, None] = {}
    for tpl in engines:
        engine_host = urlsplit(tpl.format(q="x")).hostname
        try:
            token_qs = ""
            try:
                home = fetch(f"http://{engine_host}/").body.decode("utf-8", "replace")
                pairs = re.findall(r'<input[^>]+type="hidden"[^>]+name="([^"]+)"[^>]+value="([^"]*)"', home)
                token_qs = "".join(f"&{quote_plus(k)}={quote_plus(v)}" for k, v in pairs)
            except Exception:
                pass  # engine without a home-page token: query directly
            res = fetch(tpl.format(q=quote_plus(query)) + token_qs)
        except Exception as exc:
            if errors is not None:
                errors.append(f"{engine_host}: {type(exc).__name__}: {exc}")
            continue
        body = unquote(unquote(res.body.decode("utf-8", "replace")))
        for m in _ONION_RE.finditer(body):
            host = m.group(1).lower()
            if host != engine_host:
                found.setdefault(f"http://{host}/", None)
            if len(found) >= limit:
                break
    return list(found)
