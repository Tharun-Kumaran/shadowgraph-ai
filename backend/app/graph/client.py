"""Thin wrapper around the official Neo4j driver.

* Lazily connects so the API can start while Neo4j is still booting.
* ``read()`` runs in a READ-access transaction (server rejects writes).
* Every query carries a server-side timeout.
* Driver exceptions are mapped to application errors with safe messages.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from neo4j import READ_ACCESS, WRITE_ACCESS, Driver, GraphDatabase, ManagedTransaction, Query
from neo4j.exceptions import AuthError, ClientError, DriverError, Neo4jError, ServiceUnavailable, SessionExpired

from app.core.config import Settings
from app.core.logging import get_logger

log = get_logger(__name__)


class GraphUnavailableError(RuntimeError):
    """Neo4j cannot be reached or authentication failed."""


class GraphQueryError(RuntimeError):
    """A query was rejected by the database."""


def _to_native(value: Any) -> Any:
    """Convert neo4j temporal types and nested containers to plain Python."""
    if hasattr(value, "to_native"):
        try:
            return value.to_native()
        except Exception:  # pragma: no cover
            return str(value)
    if isinstance(value, dict):
        return {k: _to_native(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_native(v) for v in value]
    return value


class Neo4jClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._driver: Driver | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------ driver --
    def _get_driver(self) -> Driver:
        if self._driver is None:
            with self._lock:
                if self._driver is None:
                    s = self.settings
                    self._driver = GraphDatabase.driver(
                        s.neo4j_uri,
                        auth=(s.neo4j_user, s.neo4j_password.get_secret_value()),
                        connection_timeout=s.neo4j_connect_timeout_s,
                        max_transaction_retry_time=10.0,
                        connection_acquisition_timeout=s.neo4j_connect_timeout_s * 2,
                    )
        return self._driver

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def health(self) -> dict[str, Any]:
        try:
            drv = self._get_driver()
            drv.verify_connectivity()
            info = drv.get_server_info()
            return {"status": "ok", "server": info.agent, "protocol": ".".join(map(str, info.protocol_version))}
        except AuthError:
            return {"status": "error", "detail": "authentication failed (check SHADOWGRAPH_NEO4J_PASSWORD)"}
        except (ServiceUnavailable, SessionExpired, DriverError, OSError) as exc:
            return {"status": "unavailable", "detail": type(exc).__name__}

    # ------------------------------------------------------------ queries --
    def _run(self, mode: str, work: Callable[[ManagedTransaction], Any]) -> Any:
        try:
            with self._get_driver().session(database=self.settings.neo4j_database, default_access_mode=mode) as session:
                if mode == READ_ACCESS:
                    return session.execute_read(work)
                return session.execute_write(work)
        except AuthError as exc:
            raise GraphUnavailableError("Neo4j authentication failed") from exc
        except (ServiceUnavailable, SessionExpired, OSError) as exc:
            raise GraphUnavailableError("Neo4j is unavailable") from exc
        except ClientError as exc:
            log.warning("neo4j client error: %s", exc.code)
            raise GraphQueryError(f"Query rejected by database ({exc.code})") from exc
        except (Neo4jError, DriverError) as exc:
            raise GraphUnavailableError(f"Neo4j error: {type(exc).__name__}") from exc

    def read(self, text: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        def work(tx: ManagedTransaction):
            return [_to_native(r.data()) for r in tx.run(text, params or {})]

        return self._run(READ_ACCESS, work)

    def write(self, text: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        def work(tx: ManagedTransaction):
            return [_to_native(r.data()) for r in tx.run(text, params or {})]

        return self._run(WRITE_ACCESS, work)

    def write_many(self, statements: list[tuple[str, dict[str, Any]]]) -> list[list[dict[str, Any]]]:
        """Run several parameterised statements atomically in one transaction."""
        def work(tx: ManagedTransaction):
            return [[_to_native(r.data()) for r in tx.run(t, p)] for t, p in statements]

        return self._run(WRITE_ACCESS, work)
