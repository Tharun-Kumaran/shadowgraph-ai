"""
Automated unit and integration tests for the CTI Collection Pipeline.
Uses local mock HTTP servers and responses to test:
- SSRF prevention (loopback, private ranges, metadata IPs, non-https schemes)
- Collector success, timeouts, content-type checks, and size limits
- Tor status checks and safe Tor proxy validation
- Parsing, indicator extraction, and observation normalization from collected feeds
- Provenance tracking (distinguishing live feed/tor from synthetic/imported data)
"""

from __future__ import annotations

import io
import json
import socket
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from typing import Generator
import pytest
import requests

from app.core.config import Settings
from app.ingestion.collectors import CollectionError, hardened_fetch
from app.ingestion.pipeline import CollectionPipeline, is_onion_url, validate_source_url
from app.ingestion.tor_collector import safe_fetch_onion


# --- Mock HTTP Server Fixture ---

class MockServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/feed.json":
            data = json.dumps([
                {
                    "id": "LIVE-FEED-001",
                    "author": "APT_ShadowOperator",
                    "text": "New C2 infrastructure identified for CVE-2024-3400 at 198.51.100.99 and wallet 0x52908400098527886E0F7030069857D2E4169EE7",
                    "timestamp": "2026-03-12T10:00:00Z"
                }
            ]).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif self.path == "/huge-payload":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            chunk = b"A" * 65536
            try:
                for _ in range(35):
                    self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass
        elif self.path == "/forbidden-type":
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.end_headers()
            self.wfile.write(b"\x00\x01\x02\x03")
        elif self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/feed.json")
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Quiet during tests


@pytest.fixture(scope="module")
def mock_http_server() -> Generator[str, None, None]:
    # Find free port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    server = HTTPServer(("127.0.0.1", port), MockServerHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield f"http://127.0.0.1:{port}"

    server.shutdown()
    server.server_close()


# --- Tests: SSRF & URL Validation ---

def test_ssrf_rejects_loopback():
    with pytest.raises(CollectionError, match="SSRF check"):
        validate_source_url("https://127.0.0.1/admin")
    with pytest.raises(CollectionError, match="SSRF check"):
        validate_source_url("https://localhost/metrics")


def test_ssrf_rejects_cloud_metadata():
    with pytest.raises(CollectionError, match="SSRF check"):
        validate_source_url("https://169.254.169.254/latest/meta-data/")


def test_ssrf_rejects_private_networks():
    with pytest.raises(CollectionError, match="SSRF check"):
        validate_source_url("https://192.168.1.1/router")
    with pytest.raises(CollectionError, match="SSRF check"):
        validate_source_url("https://10.0.0.5/api")


def test_ssrf_rejects_insecure_http_by_default():
    with pytest.raises(CollectionError, match="Scheme 'http' not permitted"):
        validate_source_url("http://external-threat-feed.com/iocs.json")


def test_onion_source_validation():
    onion_url = "http://2gzyxa5ihm7nsggfxnu52r2n2w6urqcm3gsgahsnq6chnbau2sm27gad.onion/feed"
    assert is_onion_url(onion_url) is True

    # When Tor is disabled in config
    with pytest.raises(CollectionError, match="Tor/.onion source access is currently disabled"):
        validate_source_url(onion_url, allow_onion=False)

    # When Tor is enabled
    clean_url, is_onion = validate_source_url(onion_url, allow_onion=True)
    assert is_onion is True
    assert clean_url == onion_url


# --- Tests: Hardened Fetching (Timeouts, Types, Size limits) ---

def test_hardened_fetch_refuses_redirect(mock_http_server):
    session = requests.Session()
    with pytest.raises(CollectionError, match="redirect refused"):
        hardened_fetch(session, f"{mock_http_server}/redirect", allowed_schemes=frozenset({"http"}))


def test_hardened_fetch_refuses_disallowed_content_type(mock_http_server):
    session = requests.Session()
    with pytest.raises(CollectionError, match="content type not allowed"):
        hardened_fetch(session, f"{mock_http_server}/forbidden-type", allowed_schemes=frozenset({"http"}))


def test_hardened_fetch_enforces_max_bytes(mock_http_server):
    session = requests.Session()
    with pytest.raises(CollectionError, match="response exceeded"):
        hardened_fetch(
            session,
            f"{mock_http_server}/huge-payload",
            allowed_schemes=frozenset({"http"}),
            max_bytes=100000,  # 100 KB limit
        )


# --- Tests: Tor SOCKS5 Safety & Proxy Requirement ---

def test_tor_collector_requires_socks5h():
    onion_url = "http://2gzyxa5ihm7nsggfxnu52r2n2w6urqcm3gsgahsnq6chnbau2sm27gad.onion/feed"
    # Testing with standard socks5:// (which causes local DNS leak) must be rejected
    with pytest.raises(CollectionError, match="proxy must use socks5h://"):
        safe_fetch_onion(onion_url, proxy="socks5://127.0.0.1:9050")


def test_tor_status_reporting_when_offline():
    settings = Settings(tor_enabled=True, tor_proxy="socks5h://127.0.0.1:59999")
    mock_neo4j = type("MockNeo4j", (), {})()
    pipeline = CollectionPipeline(settings, mock_neo4j)
    status = pipeline.check_tor_status()
    assert status["configured"] is True
    assert status["enabled"] is True
    assert status["reachable"] is False
    assert "unreachable" in status["message"]


# --- Tests: End-to-end Collection, Ingestion & Indicator Extraction ---

def test_live_feed_collection_and_neo4j_ingestion(mock_http_server):
    settings = Settings(api_key="test-key", max_upload_bytes=1000000)
    
    # In-memory mock repository to verify store_observation calls
    stored_obs = []
    class MockRepo:
        def store_observation(self, obs):
            stored_obs.append(obs)
    
    mock_neo4j = type("MockNeo4j", (), {"read": lambda *args: [], "write": lambda *args: []})()
    pipeline = CollectionPipeline(settings, mock_neo4j)
    pipeline.repo = MockRepo()
    pipeline._refresh_identity_clues = lambda: None  # Skip clue refresh for unit test

    report = pipeline.collect_and_ingest(
        f"{mock_http_server}/feed.json",
        source_id="mock-cti-feed",
        allow_test_mock=True,
    )

    assert report.total_records == 1
    assert report.accepted == 1
    assert len(stored_obs) == 1

    obs = stored_obs[0]
    assert obs.observation_id == "LIVE-FEED-001"
    assert obs.author_handle == "APT_ShadowOperator"
    assert obs.source_type == "feed"
    assert obs.synthetic is False

    # Verify indicators extracted
    entity_types = {e["type"] for e in obs.entities}
    assert "cve" in entity_types
    assert "ip_address" in entity_types
    assert "wallet" in entity_types
