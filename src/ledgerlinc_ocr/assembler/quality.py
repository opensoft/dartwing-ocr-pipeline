"""Deterministic `quality_summary` derivation (research Decisions 6, 8; US4).

Stage 1 policy `0.1.0`:
    overall = round(clip(0.5 * company_name.confidence
                         + 0.5 * mean(secondary_confidences, default 0.0),
                         0.0, 1.0),
                    4)
"""

from __future__ import annotations

SECONDARY_ENUM_ORDER = [
    "address",
    "ein",
    "state_tax_id",
    "vat_id",
    "other_tax_id",
    "website",
    "phone",
    "email",
]


def derive_secondary_identifiers(extractor: dict) -> list[str]:
    """Return `secondary_identifiers_found` in schema-enum order (FR-020)."""
    vc = extractor["vendor_candidate"]
    found: set[str] = set()

    addr = vc["address"]
    if (
        addr["city"]["value"] is not None and len(addr["city"]["evidence"]) > 0
        and addr["state"]["value"] is not None and len(addr["state"]["evidence"]) > 0
        and addr["postal_code"]["value"] is not None and len(addr["postal_code"]["evidence"]) > 0
    ):
        found.add("address")

    for slot in ("ein", "state_tax_id", "vat_id", "other_tax_id"):
        field = vc["tax_ids"][slot]
        if field["value"] is not None and len(field["evidence"]) > 0:
            found.add(slot)

    for slot in ("website", "phone", "email"):
        field = vc[slot]
        if field["value"] is not None and len(field["evidence"]) > 0:
            found.add(slot)

    return [ident for ident in SECONDARY_ENUM_ORDER if ident in found]


def compute_overall_vendor_confidence(extractor: dict, secondary_ids: list[str]) -> float:
    vc = extractor["vendor_candidate"]
    cn_conf = vc["company_name"]["confidence"]

    secondary_confs: list[float] = []
    for ident in secondary_ids:
        if ident == "address":
            secondary_confs.append(
                (
                    vc["address"]["city"]["confidence"]
                    + vc["address"]["state"]["confidence"]
                    + vc["address"]["postal_code"]["confidence"]
                )
                / 3.0
            )
        elif ident in ("ein", "state_tax_id", "vat_id", "other_tax_id"):
            secondary_confs.append(vc["tax_ids"][ident]["confidence"])
        else:
            secondary_confs.append(vc[ident]["confidence"])

    secondary_mean = (
        sum(secondary_confs) / len(secondary_confs) if secondary_confs else 0.0
    )
    raw = 0.5 * cn_conf + 0.5 * secondary_mean
    clipped = max(0.0, min(1.0, raw))
    return round(clipped, 4)


def build_quality_summary(extractor: dict) -> dict:
    secondary_ids = derive_secondary_identifiers(extractor)
    overall = compute_overall_vendor_confidence(extractor, secondary_ids)
    cn = extractor["vendor_candidate"]["company_name"]
    explicit_name_found = bool(cn["present"]) and not bool(cn["inferred"])
    return {
        "overall_vendor_confidence": overall,
        "explicit_name_found": explicit_name_found,
        "consensus_level": "single_voter_baseline",
        "secondary_identifiers_found": secondary_ids,
    }
