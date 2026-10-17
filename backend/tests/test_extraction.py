from __future__ import annotations

import pytest

from app.extraction import validators as v
from app.extraction.extractor import ExtractionPipeline, GazetteerExtractor, RegexExtractor, default_pipeline
from app.models.entities import EntityType

TOX = v.make_tox_id("AB" * 32, "DEADBEEF")


def ents(text: str, etype: EntityType | None = None):
    out = default_pipeline().run(text).entities
    return [e for e in out if etype is None or e.type == etype]


def values(text: str, etype: EntityType):
    return [e.value for e in ents(text, etype)]


# ------------------------------------------------------------------ CVE ---
@pytest.mark.parametrize("text,expected", [
    ("see CVE-2024-3400 now", ["CVE-2024-3400"]),
    ("lower cve-2023-12345 ok", ["CVE-2023-12345"]),
    ("CVE-2021-44228.", ["CVE-2021-44228"]),
])
def test_cve_valid(text, expected):
    assert values(text, EntityType.CVE) == expected
    assert all(e.valid for e in ents(text, EntityType.CVE))


@pytest.mark.parametrize("text", ["CVE-2024-123", "XCVE-2024-1234", "CVE-24-1234", "CVE-2024-1234-extra"])
def test_cve_lookalikes_not_matched(text):
    assert values(text, EntityType.CVE) == []


def test_cve_invalid_year_and_leading_zero_flagged():
    (e,) = ents("CVE-1988-1234", EntityType.CVE)
    assert not e.valid and "year" in e.notes[0]
    (e,) = ents("CVE-2020-01234", EntityType.CVE)
    assert not e.valid


# --------------------------------------------------------------- wallets ---
def test_eth_address_normalised_and_boundaries():
    addr = "0x52908400098527886E0F7030069857D2E4169EE7"
    (e,) = ents(f"pay {addr} now", EntityType.WALLET)
    assert e.value == addr.lower() and e.subtype == "evm"
    assert values("0x" + "a" * 41, EntityType.WALLET) == []  # too long
    assert values("0x" + "a" * 39, EntityType.WALLET) == []  # too short


def test_eth_not_misread_as_sha1():
    text = "0x52908400098527886e0f7030069857d2e4169ee7"
    assert values(text, EntityType.FILE_HASH) == []


@pytest.mark.parametrize("addr,subtype", [
    ("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "btc_base58"),
    ("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy", "btc_base58"),
    ("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4", "btc_bech32"),
    ("bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0", "btc_bech32"),
])
def test_bitcoin_valid(addr, subtype):
    (e,) = ents(f"addr: {addr}", EntityType.WALLET)
    assert e.subtype == subtype


def test_bitcoin_bad_checksum_rejected():
    assert values("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNb", EntityType.WALLET) == []
    assert values("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t5", EntityType.WALLET) == []


# ------------------------------------------------------------------- Tox ---
def test_tox_valid_checksum():
    (e,) = ents(f"tox: {TOX}", EntityType.TOX_ID)
    assert e.valid and e.value == TOX and len(e.value) == 76


def test_tox_lowercase_normalised_upper():
    assert values(TOX.lower(), EntityType.TOX_ID) == [TOX]


def test_tox_bad_checksum_flagged_invalid():
    bad = TOX[:-1] + ("0" if TOX[-1] != "0" else "1")
    (e,) = ents(bad, EntityType.TOX_ID)
    assert not e.valid


@pytest.mark.parametrize("n", [75, 77])
def test_tox_wrong_length(n):
    assert values("A1" * 40, EntityType.TOX_ID) == []  # 80 chars
    assert values(("AB" * 40)[:n], EntityType.TOX_ID) == []


def test_sha256_not_extracted_from_inside_tox():
    assert values(TOX, EntityType.FILE_HASH) == []


# ------------------------------------------------------------------ UUID ---
def test_uuid():
    u = "123E4567-E89B-12D3-A456-426614174000"
    assert values(f"id={u}", EntityType.UUID) == [u.lower()]
    assert values("123e4567-e89b-12d3-a456-42661417400", EntityType.UUID) == []
    assert values("123e4567-e89b-12d3-a456-4266141740000", EntityType.UUID) == []


# ----------------------------------------------------------- PGP / hash ---
def test_pgp_grouped_and_context():
    fpr = "A1B2 C3D4 E5F6 0718 293A 4B5C 6D7E 8F90 A1B2 C3D4"
    (e,) = ents(f"PGP: {fpr}", EntityType.PGP_FINGERPRINT)
    assert e.value == fpr.replace(" ", "")
    contiguous = "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4"
    assert values(f"my pgp fingerprint {contiguous}", EntityType.PGP_FINGERPRINT) == [contiguous.upper()]
    assert values(f"my pgp fingerprint {contiguous}", EntityType.FILE_HASH) == []


@pytest.mark.parametrize("h,algo", [
    ("d41d8cd98f00b204e9800998ecf8427e", "md5"),
    ("da39a3ee5e6b4b0d3255bfef95601890afd80709", "sha1"),
    ("E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855", "sha256"),
])
def test_hashes(h, algo):
    (e,) = ents(f"sample {h} dropped", EntityType.FILE_HASH)
    assert e.subtype == algo and e.value == h.lower() and e.valid


def test_hash_low_entropy_flagged_and_wrong_lengths_ignored():
    (e,) = ents("0" * 64, EntityType.FILE_HASH)
    assert not e.valid
    assert values("ab" * 17, EntityType.FILE_HASH) == []  # 34 hex chars


# ------------------------------------------------------- network / urls ---
def test_domains_and_file_extension_lookalikes():
    assert values("visit evil-example.com today", EntityType.DOMAIN) == ["evil-example.com"]
    assert values("run loader.exe and config.php and archive.zip", EntityType.DOMAIN) == []
    assert values("version 1.2.3", EntityType.DOMAIN) == []
    assert values("mail me at a@hidden.net", EntityType.DOMAIN) == []


def test_defanged_indicators():
    found = ents("hxxps://bad[.]example[.]org/payload and 198[.]51[.]100[.]7")
    vals = {(e.type, e.value) for e in found}
    assert (EntityType.URL, "https://bad.example.org/payload") in vals
    assert (EntityType.DOMAIN, "bad.example.org") in vals
    assert (EntityType.IP_ADDRESS, "198.51.100.7") in vals


def test_url_trailing_punctuation_stripped():
    assert values("(see https://example.com/a?b=1).", EntityType.URL) == ["https://example.com/a?b=1"]


def test_ipv4_validation():
    assert values("8.8.8.8", EntityType.IP_ADDRESS) == ["8.8.8.8"]
    assert values("999.1.1.1 and 1.2.3", EntityType.IP_ADDRESS) == []
    assert values("1.2.3.4.5", EntityType.IP_ADDRESS) == []
    (e,) = ents("10.0.0.5", EntityType.IP_ADDRESS)
    assert "private address" in e.notes


def test_ipv6_and_time_lookalikes():
    assert values("c2 at 2001:db8::1", EntityType.IP_ADDRESS) == ["2001:db8::1"]
    assert values("meet at 12:30:45", EntityType.IP_ADDRESS) == []
    assert values("mac aa:bb:cc:dd:ee:ff", EntityType.IP_ADDRESS) == []


# ------------------------------------------------- handles / gazetteer ---
def test_mentions_not_emails():
    assert values("ping @pepela and mail x@spirigatito.com", EntityType.HANDLE) == ["pepela"]


def test_gazetteer_aliases_canonicalised():
    found = ents("BlackCat affiliate using Qbot against Contoso via NetScaler")
    vals = {(e.type, e.value) for e in found}
    assert (EntityType.MALWARE, "ALPHV") in vals
    assert (EntityType.MALWARE, "QakBot") in vals
    assert (EntityType.ORGANIZATION, "Contoso Health") in vals
    assert (EntityType.PRODUCT, "Citrix NetScaler") in vals
    assert values("BlackCatty", EntityType.MALWARE) == []


# ------------------------------------------------------- robustness ---
def test_duplicates_deduplicated():
    text = "CVE-2024-3400 cve-2024-3400 CVE-2024-3400"
    assert values(text, EntityType.CVE) == ["CVE-2024-3400"]


def test_unicode_and_malformed_text():
    text = "Ünïcödé 🚀 \x00\ufffd CVE-2024-3400 – ０x123 \u202e evil.com"
    found = ents(text)
    assert ("CVE-2024-3400") in [e.value for e in found]
    assert ents("") == []
    assert ents("\x00\x01\x02") == []


def test_fullwidth_digits_not_matched_as_cve():
    assert values("CVE-２０２４-３４００", EntityType.CVE) == []


def test_pipeline_is_pluggable():
    p = ExtractionPipeline([RegexExtractor()])
    assert p.run("LockBit CVE-2024-3400").counts == {"cve": 1}
    g = GazetteerExtractor({EntityType.MALWARE: {"x-test": "XTest"}})
    assert [e.value for e in ExtractionPipeline([g]).run("uses x-test").entities] == ["XTest"]
