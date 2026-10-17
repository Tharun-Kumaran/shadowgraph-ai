"""
Unified Ingestion and Collection Pipeline Service.

Connects:
Configured source -> Source validation (SSRF / Scheme / Host) -> Tor/HTTP Collector
  -> Content validation -> Observation normalization -> Indicator extraction
  -> Neo4j ingestion -> Automatic Clue Candidate Generation -> Live Presentation.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

import requests

from app.core.config import Settings
from app.core.logging import get_logger
from app.correlation.candidates import generate_clues
from app.correlation.scoring import EntityRef, HandleProfile, PostSummary, ScoringConfig
from app.graph.client import Neo4jClient
from app.graph.repository import GraphRepository
from app.ingestion.collectors import CollectionError, FetchResult, hardened_fetch
from app.ingestion.normalizer import normalize_record
from app.ingestion.parsers import decode_bytes, detect_format, parse_content
from app.ingestion.tor_collector import ONION_V3, safe_fetch_onion
from app.models.entities import EntityType
from app.schemas.observations import IngestReport, Observation, RejectedRecord

log = get_logger(__name__)

# SSRF Blocked Networks (Private, loopback, link-local, carrier-grade NAT, metadata service)
BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local & Cloud Metadata (169.254.169.254)
    ipaddress.ip_network("100.64.0.0/10"),   # Shared address space / CGNAT
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),        # Unique local address
    ipaddress.ip_network("fe80::/10"),       # IPv6 link-local
]


def validate_source_url(
    url: str,
    *,
    allow_onion: bool = False,
    allow_localhost: bool = False,
    allow_http: bool = False,
) -> tuple[str, bool]:
    """
    Validate source URL against SSRF and unauthorized network access.
    Returns: (cleaned_url, is_onion)
    Raises: CollectionError if invalid.
    """
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()

    if not host:
        raise CollectionError("Source URL missing valid hostname")

    # Onion handling
    if ONION_V3.match(host):
        if not allow_onion:
            raise CollectionError("Tor/.onion source access is currently disabled in configuration")
        if scheme not in ("http", "https"):
            raise CollectionError("Onion sources require http or https scheme")
        return url, True

    # Standard Web URL handling
    allowed_schemes = ("https", "http") if (allow_localhost or allow_http) else ("https",)
    if scheme not in allowed_schemes:
        raise CollectionError(f"Scheme '{scheme}' not permitted for public collection (https required)")

    # Test for localhost / loopback string names
    if host in ("localhost", "127.0.0.1", "::1") and not allow_localhost:
        raise CollectionError("SSRF check: Access to localhost or loopback is prohibited")

    # DNS resolution check for IP range blocking (unless localhost explicitly allowed for tests)
    if not allow_localhost:
        try:
            # Resolve host to IP addresses
            addr_info = socket.getaddrinfo(host, None)
            for family, _, _, _, sockaddr in addr_info:
                ip_str = sockaddr[0]
                ip_obj = ipaddress.ip_address(ip_str)
                for blocked_net in BLOCKED_IP_NETWORKS:
                    if ip_obj in blocked_net:
                        raise CollectionError(f"SSRF check: Destination IP {ip_str} falls into prohibited network range")
        except socket.gaierror as exc:
            raise CollectionError(f"DNS resolution failed for host '{host}': {exc}") from exc

    return url, False


class CollectionPipeline:
    def __init__(self, settings: Settings, neo4j: Neo4jClient):
        self.settings = settings
        self.neo4j = neo4j
        self.repo = GraphRepository(neo4j)

    def check_tor_status(self) -> Dict[str, Any]:
        """Verify reachability of the configured Tor SOCKS5 proxy."""
        proxy_url = self.settings.tor_proxy
        if not self.settings.tor_enabled:
            return {
                "configured": False,
                "enabled": False,
                "proxy": proxy_url,
                "reachable": False,
                "message": "Tor collector is disabled in configuration (SHADOWGRAPH_TOR_ENABLED=false)",
            }

        # Test socket connectivity to Tor SOCKS5 proxy port
        try:
            parts = urlsplit(proxy_url)
            host = parts.hostname or "127.0.0.1"
            port = parts.port or 9050
            with socket.create_connection((host, port), timeout=3.0):
                return {
                    "configured": True,
                    "enabled": True,
                    "proxy": proxy_url,
                    "reachable": True,
                    "message": f"Tor SOCKS5 proxy reachable at {host}:{port}",
                }
        except Exception as exc:
            return {
                "configured": True,
                "enabled": True,
                "proxy": proxy_url,
                "reachable": False,
                "message": f"Tor proxy unreachable at {proxy_url}: {type(exc).__name__}",
            }

    def collect_and_ingest(
        self,
        url: str,
        *,
        source_id: Optional[str] = None,
        source_name: Optional[str] = None,
        allow_test_mock: bool = False,
        session: Optional[requests.Session] = None,
    ) -> IngestReport:
        """
        Executes end-to-end collection workflow:
        1. Validate source URL & SSRF safeguards
        2. Fetch content using Tor or hardened HTTPS collector
        3. Parse & validate content
        4. Normalize observation records
        5. Ingest into Neo4j
        6. Recompute candidate identity clues
        """
        # Step 1: Validate URL
        clean_url, is_onion = validate_source_url(
            url,
            allow_onion=self.settings.tor_enabled or is_onion_url(url),
            allow_localhost=allow_test_mock,
            allow_http=allow_test_mock,
        )

        source_type = "tor" if is_onion else "feed"
        source_id = source_id or f"{source_type}:{urlsplit(clean_url).hostname}"
        source_name = source_name or f"Live {source_type.upper()}: {clean_url}"

        # Step 2: Collector fetch
        if is_onion:
            if not self.settings.tor_enabled and not allow_test_mock:
                raise CollectionError("Cannot collect from .onion source: Tor is disabled on this instance")
            fetch_res = safe_fetch_onion(
                clean_url,
                proxy=self.settings.tor_proxy,
                timeout=(self.settings.feed_timeout_s, self.settings.feed_timeout_s * 2),
                max_bytes=self.settings.max_upload_bytes,
                session=session,
            )
        else:
            fetch_session = session or requests.Session()
            allowed_schemes = frozenset({"https", "http"}) if allow_test_mock else frozenset({"https"})
            fetch_res = hardened_fetch(
                fetch_session,
                clean_url,
                allowed_schemes=allowed_schemes,
                timeout=(min(10.0, self.settings.feed_timeout_s), self.settings.feed_timeout_s),
                max_bytes=self.settings.max_upload_bytes,
            )

        # Step 3: Parse content
        content_text = decode_bytes(fetch_res.body)
        detected_fmt = "json" if fetch_res.content_type in ("application/json", "application/stix+json") else "text"
        records, rejected, fmt = parse_content(content_text, detected_fmt)

        # Step 4: Ingestion & Indicator Extraction
        accepted = 0
        obs_ids = []
        extraction_summary: Dict[str, int] = {}
        batch_id = f"collect_{int(datetime.now(timezone.utc).timestamp())}"

        for idx, rec in records:
            try:
                obs = normalize_record(
                    rec,
                    default_source=source_id,
                    default_source_type=source_type,
                    max_text_chars=self.settings.max_text_chars,
                    retention=self.settings.text_retention,
                    force_synthetic=False,
                )
                obs.source_url = clean_url
                self.repo.store_observation(obs)
                accepted += 1
                obs_ids.append(obs.observation_id)
                for ent in obs.entities:
                    t = ent.get("type", "unknown")
                    extraction_summary[t] = extraction_summary.get(t, 0) + 1
            except Exception as exc:
                rejected.append(RejectedRecord(index=idx, reason=str(exc)))

        # Step 5: Automatically generate and update candidate clues across active handles
        self._refresh_identity_clues()

        return IngestReport(
            batch_id=batch_id,
            filename=clean_url,
            format=fmt,
            total_records=len(records) + len(rejected),
            accepted=accepted,
            duplicates_in_batch=0,
            duplicates_existing=0,
            rejected=rejected,
            extraction_summary=extraction_summary,
            observation_ids=obs_ids,
            stored=True,
        )

    def _refresh_identity_clues(self) -> None:
        """Scan active handles and generate candidate identity resolution clues."""
        query = (
            "MATCH (h:Handle) "
            "OPTIONAL MATCH (h)-[:AUTHORED]->(p:Post) "
            "OPTIONAL MATCH (p)-[r]->(i:SGNode) "
            "WHERE type(r) IN ['MENTIONS', 'REFERENCES'] "
            "RETURN h.name AS name, collect(DISTINCT properties(p)) AS posts, "
            "collect(DISTINCT {uid: i.uid, type: i.type, value: i.value, valid: i.valid, post_id: p.post_id}) AS entities"
        )
        try:
            rows = self.neo4j.read(query)
            profiles: List[HandleProfile] = []
            for r in rows:
                name = r.get("name")
                if not name:
                    continue
                prof = HandleProfile(handle=name)
                for p in r.get("posts", []):
                    if not p:
                        continue
                    prof.posts.append(
                        PostSummary(
                            post_id=p.get("post_id", ""),
                            content_hash=p.get("content_hash", ""),
                            observed_at=p.get("observed_at"),
                            text_length=p.get("text_length", 0),
                        )
                    )
                for ent in r.get("entities", []):
                    if not ent or not ent.get("uid") or not ent.get("type"):
                        continue
                    try:
                        etype = EntityType(ent["type"])
                    except ValueError:
                        continue
                    uid = ent["uid"]
                    if uid not in prof.entities:
                        prof.entities[uid] = EntityRef(
                            uid=uid,
                            type=etype,
                            value=ent.get("value", ""),
                            valid=ent.get("valid", True),
                        )
                    if ent.get("post_id"):
                        prof.entities[uid].post_ids.add(ent["post_id"])
                profiles.append(prof)

            if len(profiles) >= 2:
                cfg = ScoringConfig(
                    candidate_threshold=self.settings.clue_candidate_threshold,
                    high_priority_threshold=self.settings.clue_high_priority_threshold,
                )
                clues = generate_clues(profiles, cfg)
                for cl in clues:
                    self.repo.save_clue(cl)
        except Exception as exc:
            log.warning("Could not auto-refresh identity clues: %s", exc)


def is_onion_url(url: str) -> bool:
    try:
        host = (urlsplit(url).hostname or "").lower()
        return bool(ONION_V3.match(host))
    except Exception:
        return False
