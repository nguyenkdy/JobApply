"""Group split protocols and explicit leakage checks before any pair sampling."""
from collections import Counter
from copy import deepcopy
import math
from pathlib import Path

from .common import (digest, file_hash, fresh_folder, read_json, read_lines, require,
                     seal, verify, write_json, write_lines)
from .grouping import group_records

PARTITIONS = ("train", "validation", "test")


def load_dataset(folder):
    folder = Path(folder)
    manifest = verify(folder, "dataset")
    records = read_lines(folder / "records.jsonl")
    groups = read_json(folder / "groups.json")
    # Recompute source/template and near links: a hash alone is not a leakage check.
    rebuilt, _ = group_records(deepcopy(records), read_lines(folder / "protected_anchors.jsonl"), manifest["near_threshold"])
    require(groups == rebuilt, "Dataset grouping does not match its documents/lineage")
    by_id = {r["record_id"]: r for r in records}
    require(len(by_id) == len(records), "Duplicate dataset record IDs")
    for group in groups:
        for rid in group["record_ids"]:
            require(by_id[rid]["group_id"] == group["group_id"] and by_id[rid]["development_only"] == group["development_only"],
                    "Record/group exposure mismatch")
    return manifest, records, groups


def allocate(groups, seed, kind, ratios):
    ordered = sorted(groups, key=lambda g: (digest(f"{seed}|{kind}|{g}"), g))
    n = len(ordered)
    # Allocate whole groups. With >=3 groups reserve one per partition first;
    # otherwise make incompleteness explicit, never split a family to fill quotas.
    minimum = [1, 1, 1] if n >= 3 else [int(n >= 1), int(n >= 2), 0]
    remainder = n - sum(minimum)
    targets = [remainder * ratio for ratio in ratios]
    counts = [minimum[i] + math.floor(targets[i]) for i in range(3)]
    for i in sorted(range(3), key=lambda i: (-(targets[i] % 1), i))[:n-sum(counts)]:
        counts[i] += 1
    assigned, start = {}, 0
    for partition, count in zip(PARTITIONS, counts):
        assigned.update({group: partition for group in ordered[start:start+count]})
        start += count
    return assigned


def assignments_for(records, mode, seed, ratios):
    require(mode in {"known-jd", "new-both"}, "mode must be known-jd or new-both")
    require(len(ratios) == 3 and all(type(r) in (int, float) and 0 < r < 1 for r in ratios)
            and math.isclose(sum(ratios), 1, abs_tol=1e-9), "Three positive split ratios must sum to one")
    group_partitions = {}
    for kind in ("cv", "jd"):
        groups = {r["group_id"] for r in records if r["kind"] == kind and r["decision"] == "keep" and not r["development_only"]}
        group_partitions.update({g: "shared" for g in groups} if kind == "jd" and mode == "known-jd"
                                else allocate(groups, seed, kind, ratios))
    assignments = []
    for row in records:
        partition = ("excluded" if row["decision"] != "keep" else "development" if row["development_only"]
                     else group_partitions[row["group_id"]])
        assignments.append(dict(record_id=row["record_id"], kind=row["kind"], group_id=row["group_id"], partition=partition))
    return assignments


def audit_assignments(records, groups, assignments, mode):
    by_id = {r["record_id"]: r for r in records}
    mapping = {r["record_id"]: r for r in assignments}
    errors = []
    if len(mapping) != len(assignments) or set(mapping) != set(by_id):
        errors.append("Assignment IDs missing/duplicate/unknown")
    for rid, assignment in mapping.items():
        if rid not in by_id:
            continue
        row = by_id[rid]
        p = assignment["partition"]
        if assignment["kind"] != row["kind"] or assignment["group_id"] != row["group_id"]:
            errors.append("Assignment metadata mismatch:" + rid)
        if row["decision"] != "keep" and p != "excluded":
            errors.append("Excluded/quarantined record used:" + rid)
        if row["development_only"] and p not in {"development", "excluded"}:
            errors.append("Viewed pilot/development family leaked:" + rid)
        allowed = {"development", "excluded"} | ({"shared"} if row["kind"] == "jd" and mode == "known-jd" else set(PARTITIONS))
        if p not in allowed:
            errors.append("Partition incompatible with evaluation protocol:" + rid)
    for group in groups:
        destinations = {mapping[rid]["partition"] for rid in group["record_ids"] if rid in mapping
                        and mapping[rid]["partition"] != "excluded"}
        if len(destinations) > 1:
            errors.append("Source/template/exact/near family crosses partitions:" + group["group_id"])
    counts = {kind: dict(Counter(r["partition"] for r in assignments if r["kind"] == kind)) for kind in ("cv", "jd")}
    missing = []
    for p in PARTITIONS:
        if counts["cv"].get(p, 0) == 0:
            missing.append("no_CV_in_" + p)
        if counts["jd"].get("shared" if mode == "known-jd" else p, 0) < 5:
            missing.append("fewer_than_5_JD_for_" + p)
    return dict(leakage_check_passed=not errors, errors=errors, counts=counts, partition_ready=not missing and not errors,
                readiness_blockers=missing, final_test_ready=False, labels_available=False,
                note="Structural partition checks only; no verified labels, identity verification or semantic dedup guarantee")


def make_split(dataset, output, mode="known-jd", seed=20261113, ratios=(0.6, 0.2, 0.2)):
    dataset = Path(dataset).resolve()
    manifest, records, groups = load_dataset(dataset)
    assignments = assignments_for(records, mode, seed, ratios)
    audit = audit_assignments(records, groups, assignments, mode)
    require(audit["leakage_check_passed"], str(audit["errors"]))
    folder = fresh_folder(output, (dataset,))
    write_lines(folder / "assignments.jsonl", assignments)
    write_json(folder / "leakage_report.json", audit)
    by_id = {r["record_id"]: r for r in records}
    write_json(folder / "distributions.json", {
        p: {kind: dict(Counter(by_id[r["record_id"]]["role"] or "unknown" for r in assignments
                              if r["partition"] == p and r["kind"] == kind)) for kind in ("cv", "jd")}
        for p in (*PARTITIONS, "shared", "development", "excluded")})
    seal(folder, "split", dict(dataset_manifest_sha256=file_hash(dataset / "manifest.json"), dataset_version=manifest["dataset_version"],
                                mode=mode, seed=seed, ratios=list(ratios), ranking_k=5,
                                allocation="seeded whole groups; minimum one per partition if >=3; remaining groups by largest remainder",
                                evaluation_scope="new CV on a shared known JD catalogue; no claim of new-JD generalization"
                                if mode == "known-jd" else "both CV and JD groups disjoint across train/validation/test",
                                pilot_policy="viewed pilot and connected families outside train/validation/test/shared",
                                label_status="unlabeled; final test not ready"))
    return audit


def audit_split(dataset, split):
    dataset, split = Path(dataset), Path(split)
    manifest, records, groups = load_dataset(dataset)
    receipt = verify(split, "split")
    require(receipt["dataset_manifest_sha256"] == file_hash(dataset / "manifest.json")
            and receipt["dataset_version"] == manifest["dataset_version"], "Split belongs to a different dataset version")
    assignments = read_lines(split / "assignments.jsonl")
    report = audit_assignments(records, groups, assignments, receipt["mode"])
    expected = assignments_for(records, receipt["mode"], receipt["seed"], receipt["ratios"])
    require(assignments == expected, "Split does not reproduce its seed/protocol or contains leakage")
    require(report["leakage_check_passed"], str(report["errors"]))
    return report
