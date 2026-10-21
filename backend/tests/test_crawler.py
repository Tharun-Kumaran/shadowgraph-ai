"""Unit tests for the onion crawler (fake transport; no Tor required)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.ingestion.collectors import CollectionError, FetchResult
from app.ingestion.crawler import (
    CrawlConfig,
    OnionCrawler,
    canonicalize,
    discover_onions,
    is_unsafe,
    parse_html,
)

A = "a" * 56 + ".onion"
B = "b" * 56 + ".onion"
C = "c" * 56 + ".onion"


def _fr(url: str, body: str, ctype: str = "text/html") -> FetchResult:
    return FetchResult(url=url, status_code=200, content_type=ctype, body=body.encode(),
                       fetched_at=datetime.now(timezone.utc))


class FakeNet:
    def __init__(self, pages: dict[str, str]):
        self.pages = pages
        self.calls: list[str] = []

    def __call__(self, url: str) -> FetchResult:
        self.calls.append(url)
        if url not in self.pages:
            raise CollectionError("request failed: ConnectTimeout")
        ctype = "text/plain" if url.endswith("robots.txt") else "text/html"
        return _fr(url, self.pages[url], ctype)


def crawler(net, **kw):
    cfg = CrawlConfig(delay_s=0, jitter_s=0, respect_robots=kw.pop("robots", False), **kw)
    return OnionCrawler(net, cfg, sleep=lambda s: None)


def test_canonicalize_rules():
    assert canonicalize(f"http://{A}/x#frag") == f"http://{A}/x"
    assert canonicalize("https://example.com/") is None            # clearnet never crawled
    assert canonicalize("http://abcdefghij234567.onion/") is None  # v2 rejected
    assert canonicalize(f"http://{A}/pic.jpg") is None             # media never requested
    assert canonicalize(f"ftp://{A}/") is None


def test_parse_html_strips_scripts_and_extracts_links():
    title, text, hrefs = parse_html(
        "<html><title> Hello </title><script>evil()</script><body><p>Body text</p>"
        "<a href='/next'>n</a></body></html>"
    )
    assert title == "Hello" and "evil" not in text and "Body text" in text
    assert hrefs == ["/next"]


def test_bfs_follows_links_across_onions_and_records_edges():
    net = FakeNet({
        f"http://{A}/": f"<title>A</title>seed page <a href='/p2'>x</a> <a href='http://{B}/'>b</a>",
        f"http://{A}/p2": "second page unique content",
        f"http://{B}/": "site B content here",
    })
    res = crawler(net, max_depth=2).run([f"http://{A}/"])
    assert {p.url for p in res.pages} == {f"http://{A}/", f"http://{A}/p2", f"http://{B}/"}
    assert (A, B) in res.edges
    assert res.host_status == {A: "alive", B: "alive"}


def test_depth_and_page_caps():
    net = FakeNet({
        f"http://{A}/": "<a href='/1'>1</a> root",
        f"http://{A}/1": "<a href='/2'>2</a> one",
        f"http://{A}/2": "two",
    })
    assert len(crawler(net, max_depth=1).run([f"http://{A}/"]).pages) == 2
    res = crawler(net, max_depth=5, max_pages=1).run([f"http://{A}/"])
    assert len(res.pages) == 1 and res.stopped_reason == "max_pages"


def test_per_host_cap():
    links = "".join(f"<a href='/{i}'>x</a>" for i in range(10))
    pages = {f"http://{A}/": "root " + links, **{f"http://{A}/{i}": f"page {i}" for i in range(10)}}
    res = crawler(FakeNet(pages), max_depth=2, max_pages_per_host=3).run([f"http://{A}/"])
    assert len(res.pages) == 3


def test_dead_host_marked_and_clearnet_links_ignored():
    net = FakeNet({f"http://{A}/": f"<a href='https://example.com/'>c</a><a href='http://{C}/'>dead</a> root"})
    res = crawler(net).run([f"http://{A}/"])
    assert res.host_status[C] == "dead"
    assert all("example.com" not in c for c in net.calls)


def test_duplicate_content_skipped():
    net = FakeNet({
        f"http://{A}/": "<a href='/dup'>d</a> same",
        f"http://{A}/dup": "<a href='/dup'>d</a> same",
    })
    res = crawler(net).run([f"http://{A}/"])
    assert len(res.pages) == 1 and res.skipped_duplicates == 1


def test_robots_txt_is_honoured():
    net = FakeNet({
        f"http://{A}/robots.txt": "User-agent: *\nDisallow: /private",
        f"http://{A}/": "<a href='/private/x'>p</a><a href='/ok'>o</a> root",
        f"http://{A}/private/x": "secret",
        f"http://{A}/ok": "fine",
    })
    res = crawler(net, robots=True).run([f"http://{A}/"])
    urls = {p.url for p in res.pages}
    assert f"http://{A}/ok" in urls and f"http://{A}/private/x" not in urls


def test_safety_filter_drops_page_blocks_host_and_stops_following():
    net = FakeNet({
        f"http://{A}/": f"<a href='http://{B}/'>b</a> root",
        f"http://{B}/": "<a href='/more'>m</a> this site hosts child porn archive",
        f"http://{B}/more": "should never be fetched",
    })
    res = crawler(net).run([f"http://{A}/"])
    assert res.host_status[B] == "blocked" and res.blocked_pages == 1
    assert not any(p.host == B for p in res.pages)
    assert f"http://{B}/more" not in net.calls


def test_is_unsafe_does_not_flag_normal_text():
    assert not is_unsafe("Tor Project", "Anonymity online. Download Tor Browser.")


def test_time_budget_stops_crawl():
    ticks = iter(range(0, 1000, 100))
    net = FakeNet({f"http://{A}/": "<a href='/1'>1</a> root", f"http://{A}/1": "one"})
    cfg = CrawlConfig(delay_s=0, jitter_s=0, respect_robots=False, time_budget_s=150)
    res = OnionCrawler(net, cfg, sleep=lambda s: None, clock=lambda: next(ticks)).run([f"http://{A}/"])
    assert res.stopped_reason == "time_budget"


def test_discover_onions_extracts_hosts_and_skips_engine():
    engine = "d" * 56 + ".onion"
    body = f"<a href='/search/redirect?redirect_url=http%3A%2F%2F{B}%2Fforum'>x</a> http://{engine}/ {C}"
    net = FakeNet({f"http://{engine}/search/?q=test": body})
    found = discover_onions(net, "test", engines=[f"http://{engine}/search/?q={{q}}"])
    assert found == [f"http://{B}/", f"http://{C}/"]


def test_clamp_enforces_caps():
    cfg = CrawlConfig(max_pages=9999, max_depth=99, time_budget_s=99999).clamp(pages_cap=50, depth_cap=3, time_cap=100)
    assert (cfg.max_pages, cfg.max_depth, cfg.time_budget_s) == (50, 3, 100)
