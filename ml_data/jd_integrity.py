"""Shared invariants for metadata enrichment without changing the JD corpus."""
from .common import require

IMMUTABLE_JD_KEYS = (
    "record_id", "entity_id", "kind", "external_id", "namespace",
    "text_original", "text_normalized", "text_sha256", "normalized_text_sha256",
    "normalized_sha256", "source_group", "template_group", "is_synthetic",
    "exposure", "text_scope", "upstream_text_sha256", "decision",
    "decision_reasons", "related_source_keys", "lineage", "group_id", "development_only",
)


def assert_frozen_jd_identity_and_exposure(before, after):
    """Verify JD identity, text, gate decisions, groups and exposure after enrichment."""
    old = {r["record_id"]: r for r in before if r["kind"] == "jd"}
    new = {r["record_id"]: r for r in after if r["kind"] == "jd"}
    require(old and set(old) == set(new), "JD record ID set changed during metadata enrichment")
    for rid, old_row in old.items():
        for key in IMMUTABLE_JD_KEYS:
            require(old_row[key] == new[rid][key], f"Immutable JD field '{key}' changed for {rid}")
    return dict(
        records=len(old),
        identity_text_gate_exposure_identical=True,
        development_records=sum(r["development_only"] for r in new.values()),
        enriched_metadata_fields=["role", "skills", "stack", "experience"],
    )
