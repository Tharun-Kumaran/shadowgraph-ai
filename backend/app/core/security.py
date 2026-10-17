"""Access control for state-changing endpoints.

ShadowGraph AI is designed for a *trusted local environment*. Every
mutating endpoint requires the ``X-API-Key`` header to match
``SHADOWGRAPH_API_KEY``. If no key is configured, mutations are refused
(fail closed). This is a shared-secret control, not user authentication;
see docs/security.md.
"""

from __future__ import annotations

import hmac
import re

from fastapi import Depends, Header, HTTPException, status

from app.core.config import Settings, get_settings

_SAFE_REVIEWER = re.compile(r"^[A-Za-z0-9 ._@-]{1,64}$")


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    settings: Settings = Depends(get_settings),
) -> None:
    configured = settings.api_key.get_secret_value()
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mutations disabled: SHADOWGRAPH_API_KEY is not configured on the server.",
        )
    if not x_api_key or not hmac.compare_digest(x_api_key.encode(), configured.encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid API key.")


def sanitize_reviewer(name: str) -> str:
    name = name.strip()
    if not _SAFE_REVIEWER.match(name):
        raise ValueError("reviewer must be 1-64 chars of letters, digits, space, . _ @ -")
    return name


_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def strip_control_chars(text: str) -> str:
    return _CONTROL.sub("", text)
