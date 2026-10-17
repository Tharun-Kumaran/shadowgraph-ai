"""Core entity vocabulary shared by extraction, graph and export layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class EntityType(str, Enum):
    HANDLE = "handle"
    WALLET = "wallet"
    TOX_ID = "tox_id"
    PGP_FINGERPRINT = "pgp_fingerprint"
    CVE = "cve"
    DOMAIN = "domain"
    URL = "url"
    IP_ADDRESS = "ip_address"
    FILE_HASH = "file_hash"
    UUID = "uuid"
    MALWARE = "malware"
    ORGANIZATION = "organization"
    PRODUCT = "product"


# Technical artifacts with high specificity: shared use is *strong* evidence of
# shared artifact use (not proof of shared identity). Values are the
# specificity weight used by the artifact-overlap signal.
ARTIFACT_SPECIFICITY: dict[EntityType, float] = {
    EntityType.TOX_ID: 1.0,
    EntityType.PGP_FINGERPRINT: 1.0,
    EntityType.WALLET: 0.9,
    EntityType.UUID: 0.6,
    EntityType.FILE_HASH: 0.5,
    EntityType.URL: 0.4,
    EntityType.DOMAIN: 0.35,
    EntityType.IP_ADDRESS: 0.3,
}

# Contextual / weak entities: used for graph-neighbourhood overlap only.
CONTEXT_TYPES: frozenset[EntityType] = frozenset(
    {EntityType.CVE, EntityType.MALWARE, EntityType.ORGANIZATION, EntityType.PRODUCT}
)

# Graph label per entity type. Labels are chosen ONLY from this fixed map,
# never from user input, because Cypher labels cannot be parameterised.
ENTITY_LABELS: dict[EntityType, tuple[str, ...]] = {
    EntityType.WALLET: ("Indicator", "Wallet"),
    EntityType.TOX_ID: ("Indicator", "ToxID"),
    EntityType.PGP_FINGERPRINT: ("Indicator", "PGPFingerprint"),
    EntityType.DOMAIN: ("Indicator", "Domain"),
    EntityType.URL: ("Indicator", "URL"),
    EntityType.IP_ADDRESS: ("Indicator", "IPAddress"),
    EntityType.FILE_HASH: ("Indicator", "FileHash"),
    EntityType.UUID: ("Indicator", "UUIDIdentifier"),
    EntityType.CVE: ("CVE",),
    EntityType.MALWARE: ("Malware",),
    EntityType.ORGANIZATION: ("Organization",),
    EntityType.PRODUCT: ("Product",),
}

# Relationship from Post to entity, also from a fixed allow-list.
POST_RELATIONSHIP: dict[EntityType, str] = {
    EntityType.CVE: "REFERENCES",
}


def entity_uid(entity_type: EntityType | str, value: str) -> str:
    t = entity_type.value if isinstance(entity_type, EntityType) else entity_type
    return f"{t}:{value}"


@dataclass
class ExtractedEntity:
    type: EntityType
    value: str  # normalised value
    raw: str  # value as it appeared (after refanging)
    subtype: str | None = None
    valid: bool = True
    notes: list[str] = field(default_factory=list)
    start: int = -1
    end: int = -1

    @property
    def uid(self) -> str:
        return entity_uid(self.type, self.value)

    def to_dict(self) -> dict:
        return {
            "uid": self.uid,
            "type": self.type.value,
            "value": self.value,
            "raw": self.raw,
            "subtype": self.subtype,
            "valid": self.valid,
            "notes": list(self.notes),
        }
