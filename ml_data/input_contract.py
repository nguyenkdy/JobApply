"""Versioned bridge from immutable byte receipts to audited LF-only code differences."""
from pathlib import Path

from .common import ROOT, file_hash, read_json, require, verify
from .readiness_audit import EOL_PROOF_PATHS, compare_protected, sha_bytes

VERSION = "protected-input-contract-v2"


def contract_entry(path, data, historical_hash, audited):
    result = compare_protected(path, data, historical_hash)
    require(audited["path"] == path and audited["expected_sha256"] == historical_hash, "Audit/historical reference differs")
    if result["status"] == "byte_identical":
        result["accepted_as"] = "exact_historical_bytes"
    else:
        require(path in EOL_PROOF_PATHS and result["status"] == audited["status"] == "eol_only_proven", "Unapproved input mutation")
        require(result["canonical_lf_sha256"] == audited["canonical_lf_sha256"], "Code content differs beyond EOL")
        result["accepted_as"] = "audited_code_lf_equivalence"
    return result


def verify_inputs(intake, audit, root=ROOT):
    intake, audit, root = Path(intake), Path(audit), Path(root)
    verify(intake, "authored-cv-intake")
    verify(audit, "readiness-audit")
    summary = read_json(audit / "summary.json")
    require(summary["inputs"]["intake_manifest_sha256"] == file_hash(intake / "manifest.json"), "Audit belongs to another intake")
    protected = read_json(intake / "protected_input_hashes.json")
    proof = {r["path"]: r for r in read_json(audit / "protected_input_audit.json")["files"]}
    require(set(proof) == set(protected), "Protected input set differs from audited set")
    entries = []
    for path, expected in sorted(protected.items()):
        target = (root / path).resolve()
        require(target.is_relative_to(root.resolve()), "Protected path escapes workspace")
        entries.append(contract_entry(path, target.read_bytes(), expected, proof[path]))
    return dict(version=VERSION, intake_manifest_sha256=file_hash(intake / "manifest.json"),
                audit_manifest_sha256=file_hash(audit / "manifest.json"),
                historical_receipt_sha256=file_hash(intake / "protected_input_hashes.json"),
                entries=entries, historical_receipt_rewritten=False, original_strict_gate_modified=False,
                code_policy="Only four paths with sealed CRLF/LF proof; no whitespace/content/version change allowed",
                data_policy="Exact raw SHA256; no EOL normalization for CSV, CV/JD, evidence, or historical artifacts")


def execution_fingerprints():
    return {p.name: dict(raw_sha256=file_hash(p), lf_sha256=sha_bytes(p.read_bytes().replace(b"\r\n", b"\n")))
            for p in sorted((ROOT / "ml_data").glob("*.py"))}


def verify_execution_contract(saved, current):
    """Code may differ in newline bytes, never in LF-normalized executable text."""
    require(set(saved) == set(current), "Execution module set differs; use frozen source")
    for name in saved:
        require(saved[name]["lf_sha256"] == current[name]["lf_sha256"], "Execution code differs beyond EOL: " + name)
    return dict(compatible=True, raw_byte_differences=[name for name in sorted(saved) if saved[name]["raw_sha256"] != current[name]["raw_sha256"]])
