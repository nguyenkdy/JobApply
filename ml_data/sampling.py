"""Post-split candidates; nothing here assigns relevance or creates negatives."""
from collections import Counter
from pathlib import Path
import random

from .common import (digest, file_hash, fresh_folder, read_json, read_lines, require,
                     seal, write_csv, write_json)
from .splitting import PARTITIONS, audit_split

FIELDS = ("pair_id", "partition", "cv_id", "jd_id", "cv_version", "jd_version", "cv_text", "jd_text",
          "label_status", "relevance_0_1_2", "cv_evidence", "jd_evidence", "rationale")


def candidate_reasons(cv, jd):
    shared = set(cv["skills"]) & set(jd["skills"])
    reasons = []
    if shared and cv["role"] and jd["role"] and cv["role"] != jd["role"]:
        reasons.append("shared_skill_different_role")
    if shared and cv["role"] and cv["role"] == jd["role"] and cv["stack"] and jd["stack"] and not set(cv["stack"]) & set(jd["stack"]):
        reasons.append("shared_skill_different_stack")
    if any(scope in jd["experience"] and jd["experience"][scope] > months for scope, months in cv["experience"].items()):
        reasons.append("scoped_experience_requirement_gap")
    return reasons


def sample_pairs(dataset, split, output, partition="train", strategy="mixed", seed=20261113,
                 random_per_cv=3, hard_per_type=2, max_pairs=100000):
    dataset, split = Path(dataset).resolve(), Path(split).resolve()
    require(partition in PARTITIONS, "Choose train, validation or test")
    require(strategy in {"mixed", "census"}, "strategy must be mixed or census")
    require(partition == "train" or strategy == "census", "Validation/test require a fixed catalogue census; hard mining is train only")
    require(type(random_per_cv) is int and random_per_cv >= 1 and type(hard_per_type) is int and hard_per_type >= 0,
            "Require at least one random candidate and non-negative hard count")
    require(type(max_pairs) is int and max_pairs > 0, "max_pairs must be positive")
    audit_split(dataset, split)
    manifest = read_json(split / "manifest.json")
    records = {r["record_id"]: r for r in read_lines(dataset / "records.jsonl")}
    assignments = read_lines(split / "assignments.jsonl")
    cvs = sorted((records[r["record_id"]] for r in assignments if r["kind"] == "cv" and r["partition"] == partition), key=lambda r: r["record_id"])
    jd_partition = "shared" if manifest["mode"] == "known-jd" else partition
    jobs = sorted((records[r["record_id"]] for r in assignments if r["kind"] == "jd" and r["partition"] == jd_partition), key=lambda r: r["record_id"])
    require(cvs and jobs, "No eligible CV/JD for requested partition; supply new data, do not relabel pilot as test")
    upper_bound = len(cvs) * (len(jobs) if strategy == "census" else min(len(jobs), random_per_cv + 3 * hard_per_type))
    require(upper_bound <= max_pairs, "Pair budget exceeded; census is not silently truncated")
    pairs, selection, shortages = [], [], []
    for cv in cvs:
        rng = random.Random(digest(f"{seed}|{partition}|{cv['record_id']}"))
        chosen = {}
        if strategy == "census":
            chosen = {jd["record_id"]: "catalogue_census" for jd in jobs}
        else:
            count = min(random_per_cv, len(jobs))
            chosen.update({jd["record_id"]: "uniform_random_without_replacement" for jd in rng.sample(jobs, count)})
            if count < random_per_cv:
                shortages.append(dict(cv_id=cv["record_id"], strategy="random", requested=random_per_cv, selected=count))
            for category in ("shared_skill_different_role", "shared_skill_different_stack", "scoped_experience_requirement_gap"):
                candidates = [jd for jd in jobs if jd["record_id"] not in chosen and category in candidate_reasons(cv, jd)]
                count = min(hard_per_type, len(candidates))
                chosen.update({jd["record_id"]: category for jd in rng.sample(candidates, count)})
                if count < hard_per_type:
                    shortages.append(dict(cv_id=cv["record_id"], strategy=category, requested=hard_per_type, selected=count,
                                          reason="not enough distinct candidates with explicit metadata; no label inferred"))
        for jid, reason in sorted(chosen.items()):
            jd = records[jid]
            pid = "PAIR_" + digest(cv["record_id"] + "|" + jid)[:32]
            pairs.append(dict(pair_id=pid, partition=partition, cv_id=cv["record_id"], jd_id=jid,
                              cv_version=cv["normalized_text_sha256"], jd_version=jd["normalized_text_sha256"],
                              cv_text=cv["text_normalized"], jd_text=jd["text_normalized"], label_status="unlabeled",
                              **{key: "" for key in FIELDS[9:]}))
            selection.append(dict(pair_id=pid, selection_reason=reason, candidate_flags=candidate_reasons(cv, jd),
                                  mining_model_version=None, metadata_status="source_asserted; not label evidence"))
    random.Random(seed).shuffle(pairs)
    folder = fresh_folder(output, (dataset, split))
    (folder / "coordinator").mkdir()
    write_csv(folder / "pairs.csv", pairs, FIELDS)
    write_json(folder / "coordinator/selection.json", selection)
    summary = dict(partition=partition, strategy=strategy, cv_count=len(cvs), jd_count=len(jobs), pairs=len(pairs),
                   by_strategy=dict(Counter(r["selection_reason"] for r in selection)), shortages=shortages,
                   label_counts={"unlabeled": len(pairs)}, ranking_k=5,
                   evaluation_scope="Complete catalogue candidate grid, still unlabeled" if strategy == "census"
                   else "Sampled training candidates; not the denominator for full-catalogue Recall@5",
                   no_hard_candidate_is_a_negative=True)
    write_json(folder / "summary.json", summary)
    seal(folder, "pairs", dict(dataset_manifest_sha256=file_hash(dataset / "manifest.json"),
                                split_manifest_sha256=file_hash(split / "manifest.json"), seed=seed,
                                partition=partition, strategy=strategy, random_per_cv=random_per_cv,
                                hard_per_type=hard_per_type, ranking_k=5, labels="unlabeled"))
    return summary
