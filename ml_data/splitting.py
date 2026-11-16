"""Group split protocols and explicit leakage checks before any pair sampling."""
from collections import Counter
from copy import deepcopy
import math
from pathlib import Path
import shutil

from .common import (digest, file_hash, fresh_folder, read_json, read_lines, require,
                     seal, verify, write_json, write_lines)
from .grouping import group_records

PARTITIONS = ("train", "validation", "test")
EVAL_ROLES = ("backend python", "backend java", "frontend", "devops/cloud", "qa/testing")


def select_eval_catalogue(records, assignments, seed, per_role):
    require(type(per_role) is int and per_role >= 1, "eval_jd_per_role must be a positive integer")
    by_id = {r["record_id"]: r for r in records}
    shared_jds = [by_id[a["record_id"]] for a in assignments if a["kind"] == "jd" and a["partition"] == "shared"]
    used_groups = set()
    selected = []
    by_role_counts = {}
    for role in EVAL_ROLES:
        candidates = [j for j in shared_jds if j["role"] == role]
        chosen_role = []
        for _ in range(per_role):
            available = [j for j in candidates if j["group_id"] not in used_groups]
            if not available:
                break
            row = min(
                available,
                key=lambda j: (
                    not (bool(j["stack"]) and bool(j["skills"])),
                    not bool(j["experience"]),
                    -len(j["stack"]),
                    digest(f"eval_catalogue|{seed}|{role}|{j['record_id']}"),
                ),
            )
            used_groups.add(row["group_id"])
            chosen_role.append(dict(
                record_id=row["record_id"],
                external_id=row["external_id"],
                group_id=row["group_id"],
                role=row["role"],
                skills_count=len(row["skills"]),
                stack_count=len(row["stack"]),
                has_experience=bool(row["experience"]),
            ))
        require(len(chosen_role) == per_role, f"Insufficient independent shared JD groups for eval catalogue role '{role}': {len(chosen_role)}/{per_role}")
        by_role_counts[role] = len(chosen_role)
        selected.extend(chosen_role)
    selected.sort(key=lambda r: r["record_id"])
    return dict(
        seed=seed,
        per_role=per_role,
        total_eval_jds=len(selected),
        by_role=by_role_counts,
        record_ids=[r["record_id"] for r in selected],
        external_ids=[r["external_id"] for r in selected],
        items=selected,
        note="Fixed stratified evaluation JD catalogue (one per independent JD group) for tractable validation/test census.",
    )


def load_dataset(folder):
    folder = Path(folder)
    manifest = verify(folder, "dataset")
    records = read_lines(folder / "records.jsonl")
    for row in records:
        lineage = row.get("lineage", {})
        require(not (row["kind"] == "cv" and lineage.get("parent_ids") and not lineage.get("template_ancestors")),
                "Variant CV lacks historical template ancestry; rebuild from original assets before splitting or sampling")
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


def validate_frozen_catalogue(records, assignments, catalogue):
    by_id = {r["record_id"]: r for r in records}
    shared = {a["record_id"] for a in assignments if a["kind"] == "jd" and a["partition"] == "shared"}
    ids = catalogue["record_ids"]
    require(ids and len(ids) == len(set(ids)) and set(ids) <= shared, "Frozen catalogue includes duplicate/ineligible JD")
    require(len({by_id[rid]["group_id"] for rid in ids}) == len(ids), "Frozen catalogue repeats a JD family")
    require(catalogue["external_ids"] == [by_id[rid]["external_id"] for rid in ids], "Frozen catalogue external IDs changed")
    return len(ids)


def make_split(dataset, output, mode="known-jd", seed=20261113, ratios=(0.6, 0.2, 0.2), eval_jd_per_role=None,
               frozen_catalogue=None):
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
    extra_meta = {}
    if frozen_catalogue is not None:
        require(mode == "known-jd" and eval_jd_per_role is None, "Frozen selection cannot be combined with reselection")
        catalogue = read_json(frozen_catalogue)
        extra_meta["eval_catalogue_count"] = validate_frozen_catalogue(records, assignments, catalogue)
        shutil.copyfile(frozen_catalogue, folder / "eval_catalogue.json")
        extra_meta["frozen_catalogue_sha256"] = file_hash(frozen_catalogue)
    elif eval_jd_per_role is not None:
        require(mode == "known-jd", "eval_jd_per_role requires mode='known-jd'")
        catalogue = select_eval_catalogue(records, assignments, seed, eval_jd_per_role)
        write_json(folder / "eval_catalogue.json", catalogue)
        extra_meta["eval_jd_per_role"] = eval_jd_per_role
        extra_meta["eval_catalogue_count"] = catalogue["total_eval_jds"]
    seal(folder, "split", dict(dataset_manifest_sha256=file_hash(dataset / "manifest.json"), dataset_version=manifest["dataset_version"],
                                mode=mode, seed=seed, ratios=list(ratios), ranking_k=5,
                                allocation="seeded whole groups; minimum one per partition if >=3; remaining groups by largest remainder",
                                evaluation_scope="new CV on a shared known JD catalogue; no claim of new-JD generalization"
                                if mode == "known-jd" else "both CV and JD groups disjoint across train/validation/test",
                                pilot_policy="viewed pilot and connected families outside train/validation/test/shared",
                                label_status="unlabeled; final test not ready",
                                **extra_meta))
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
    if "eval_jd_per_role" in receipt:
        expected_cat = select_eval_catalogue(records, assignments, receipt["seed"], receipt["eval_jd_per_role"])
        actual_cat = read_json(split / "eval_catalogue.json")
        require(actual_cat == expected_cat, "Evaluation JD catalogue does not reproduce its seed/protocol")
    if "frozen_catalogue_sha256" in receipt:
        require(file_hash(split / "eval_catalogue.json") == receipt["frozen_catalogue_sha256"], "Frozen catalogue changed")
        validate_frozen_catalogue(records, assignments, read_json(split / "eval_catalogue.json"))
    require(report["leakage_check_passed"], str(report["errors"]))
    return report
