"""Format-specific validators and normalisers.

A regex match is only a *candidate*; these functions decide whether a value
is structurally valid. Structural validity still does not prove that an
indicator is malicious or even in use.
"""

from __future__ import annotations

import hashlib
import ipaddress
from datetime import datetime, timezone

# ---------------------------------------------------------------- CVE ----


def validate_cve(year: str, seq: str, now: datetime | None = None) -> tuple[bool, list[str]]:
    now = now or datetime.now(timezone.utc)
    notes: list[str] = []
    y = int(year)
    if y < 1999 or y > now.year + 1:
        notes.append(f"implausible CVE year {y}")
    if len(seq) > 4 and seq.startswith("0"):
        notes.append("sequence numbers longer than 4 digits must not have leading zeros")
    return (not notes, notes)


# --------------------------------------------------------------- Tox ----


def tox_checksum_valid(hex_id: str) -> bool:
    """Tox ID = 32B public key + 4B nospam + 2B checksum (XOR of 2-byte words)."""
    if len(hex_id) != 76:
        return False
    try:
        data = bytes.fromhex(hex_id)
    except ValueError:
        return False
    chk = [0, 0]
    for i in range(36):
        chk[i % 2] ^= data[i]
    return bytes(chk) == data[36:38]


def make_tox_id(pubkey_hex: str, nospam_hex: str) -> str:
    """Build a checksum-valid Tox ID (used for synthetic data generation)."""
    body = bytes.fromhex(pubkey_hex + nospam_hex)
    if len(body) != 36:
        raise ValueError("pubkey must be 32 bytes and nospam 4 bytes")
    chk = [0, 0]
    for i in range(36):
        chk[i % 2] ^= body[i]
    return (body + bytes(chk)).hex().upper()


# ------------------------------------------------------------ Bitcoin ----

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def base58check_valid(addr: str) -> bool:
    num = 0
    for ch in addr:
        idx = _B58.find(ch)
        if idx < 0:
            return False
        num = num * 58 + idx
    pad = len(addr) - len(addr.lstrip("1"))
    raw = num.to_bytes((num.bit_length() + 7) // 8, "big") if num else b""
    raw = b"\x00" * pad + raw
    if len(raw) != 25:
        return False
    payload, checksum = raw[:-4], raw[-4:]
    if hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4] != checksum:
        return False
    return payload[0] in (0x00, 0x05)


_BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def _bech32_polymod(values: list[int]) -> int:
    gen = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for v in values:
        top = chk >> 25
        chk = ((chk & 0x1FFFFFF) << 5) ^ v
        for i in range(5):
            chk ^= gen[i] if ((top >> i) & 1) else 0
    return chk


def bech32_valid(addr: str) -> bool:
    """BIP-173 (bech32, witness v0) / BIP-350 (bech32m, v1+) checksum check."""
    if addr.lower() != addr and addr.upper() != addr:
        return False
    addr = addr.lower()
    pos = addr.rfind("1")
    if pos < 1 or pos + 7 > len(addr) or len(addr) > 90:
        return False
    hrp, data_part = addr[:pos], addr[pos + 1 :]
    if hrp != "bc" or any(c not in _BECH32_CHARSET for c in data_part):
        return False
    data = [_BECH32_CHARSET.find(c) for c in data_part]
    expanded = [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]
    const = _bech32_polymod(expanded + data)
    witver = data[0]
    if witver == 0:
        return const == 1
    return const == 0x2BC830A3


# ----------------------------------------------------------- IP / host ----


def classify_ip(value: str) -> tuple[str | None, list[str]]:
    """Return (normalised address or None, notes)."""
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return None, []
    notes: list[str] = []
    if ip.is_unspecified:
        return None, []
    if ip.is_private:
        notes.append("private address")
    if ip.is_loopback:
        notes.append("loopback address")
    if ip.is_reserved or ip.is_multicast or ip.is_link_local:
        notes.append("reserved/multicast/link-local address")
    # RFC 5737 / RFC 3849 documentation ranges
    for net in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24", "2001:db8::/32"):
        if ip in ipaddress.ip_network(net):
            notes.append("documentation range (RFC 5737/3849)")
    return ip.compressed, notes


def hex_low_entropy(value: str) -> bool:
    return len(set(value.lower())) < 5


# Common, real TLDs accepted by the domain extractor. Deliberately excludes
# TLDs that collide with file extensions (zip, mov, sh, py, rs, pl, md) to
# reduce false positives such as "loader.zip". Extend in config if needed.
ALLOWED_TLDS: frozenset[str] = frozenset(
    """
    com net org info biz io co ai app dev xyz top online site club shop store tech cloud
    ru su ua by kz cn hk tw jp kr in pk bd lk np sg my id th vn ph au nz uk de fr nl be
    ch at it es pt pl cz sk hu ro bg gr tr ir il ae sa eg za ng ke br ar cl mx ca us eu
    se no fi dk is ie lt lv ee me tv cc ws to la gg onion int edu gov mil
    """.split()
)
