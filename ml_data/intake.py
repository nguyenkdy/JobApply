"""Admission checks for individually authored CVs; known-JD preview, no training."""
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path
import re
import shutil

from .cohort import render_profile
from .common import (ROOT, csv_rows, digest, file_hash, fresh_folder, normalize, read_json,
                     read_lines, require, seal, verify, write_csv, write_json, write_lines)
from .grouping import shingles
from .ingest import ingest, record
from .sampling import FIELDS as PAIR_FIELDS, choose_mixed
from .splitting import PARTITIONS, allocate, assignments_for, audit_assignments, load_dataset
from .synthetic import FIELDS as CV_FIELDS

VERSION = "authored-cv-intake-v1"


def admit_profiles(design, profiles):
    construction = design["construction"]
    require(construction["method"] == "individually_written_full_text" and construction["text_assembler"] is None and
            construction["shared_template"] is None, "Shared composition recipe cannot masquerade as independent authored banks")
    require(construction["shared_author_is_not_independent_collection"] is True, "Shared author limitation must remain explicit")
    require(construction["grouping_unit"] == "scenario_source_bank", "Unknown grouping basis")
    require(len(profiles) == design["expected_count"] == len({p["id"] for p in profiles}), "Wrong count/duplicate source IDs")
    require(len({p["text"] for p in profiles}) == len(profiles), "Duplicate authored source text")
    require(len(design["families"]) >= construction["minimum_source_banks"], "Too few declared banks")
    for bank in design["families"]:
        require({p["role"] for p in profiles if p["family"] == bank} == set(design["roles"]), "Bank does not cover planned roles")
    rendered = []
    for p in profiles:
        require(set(p) <= {"id", "family", "role", "kind", "text", "skills", "stack", "durations", "provenance"},
                "Unexpected slots/recipe fields in individually authored profile")
        row, ev = render_profile(p, design)
        provenance = p.get("provenance", {})
        require(not provenance.get("target_jd_ids"), "Target JD cannot drive CV authoring")
        parents, ancestors = provenance.get("parent_ids", []), provenance.get("template_ancestors", [])
        require(isinstance(ancestors, list) and isinstance(parents, list), "Lineage must be lists")
        require(all(isinstance(v, str) and v.strip() for v in parents + ancestors), "Empty/non-string lineage key")
        require(not parents or ancestors, "Variant without source/template ancestry")
        bank = design["version"] + ":source-bank:" + p["family"]
        lineage = ev["lineage"]
        lineage.update(method="Individual full-text authoring; no slot renderer; grouped conservatively by scenario source bank",
                       parent_ids=parents, template_ancestors=sorted(set(ancestors + [bank])),
                       grouping_basis="scenario_source_bank_not_claim_of_independent_authors", source_bank=p["family"],
                       template_family=None, shared_author=True, source_text_sha256=digest(p["text"]))
        row.update(source_group=design["version"] + ":scenario:" + p["id"], template_group=bank,
                   lineage_json=json.dumps(lineage, ensure_ascii=False, sort_keys=True))
        require(row["cv_text"] == p["text"], "Admission must not compose or rewrite CV prose")
        rendered.append((row, ev))
    return rendered


def lexical_diagnostics(cvs, historical):
    """Inspect actual text overlap, without presenting lexical scores as independence."""
    sets = {r["record_id"]: shingles(r["text_normalized"]) for r in cvs + historical}
    cross_bank, against_history = [], []
    for i, a in enumerate(cvs):
        for b in cvs[i+1:]:
            if a["template_group"] != b["template_group"]:
                union = sets[a["record_id"]] | sets[b["record_id"]]
                cross_bank.append((len(sets[a["record_id"]] & sets[b["record_id"]]) / len(union) if union else 1,
                                   a["record_id"], b["record_id"]))
        for b in historical:
            union = sets[a["record_id"]] | sets[b["record_id"]]
            against_history.append((len(sets[a["record_id"]] & sets[b["record_id"]]) / len(union) if union else 1,
                                    a["record_id"], b["record_id"]))
    repeated = defaultdict(set)
    for c in cvs:
        for sentence in re.split(r"[.!?\n]+", c["text_normalized"]):
            value = normalize(sentence).casefold()
            if len(value.split()) >= 12:
                repeated[value].add(c["template_group"])
    return dict(cross_bank_pairs=len(cross_bank), historical_pairs=len(against_history), historical_cv_count=len(historical),
                maximum_cross_bank_jaccard=max((v[0] for v in cross_bank), default=0),
                maximum_historical_jaccard=max((v[0] for v in against_history), default=0),
                repeated_long_sentences_across_banks=sum(len(banks) > 1 for banks in repeated.values()),
                semantic_independence_established=False,
                deleted_v5_text_comparison_performed=False,
                interpretation="Word-trigram/whole-sentence diagnostics only; shared author and domain-bank confounding remain")


def occupation_relation(a, b):
    """Conservative candidate reason; never a numeric relevance label."""
    a, b = a.casefold().strip(), b.casefold().strip()
    web = {"frontend", "fullstack", "backend python", "backend java", "backend .net", "backend php", "backend node.js", "backend ruby", "backend golang"}
    adjacent = ({"data engineer", "database/sql"}, {"data scientist", "data analyst", "ai/ml engineer"},
                {"frontend", "mobile", "desktop application"}, {"devops/cloud", "network engineering", "security engineer"})
    if not a or not b or "unspecified" in a or "unspecified" in b:
        state = "unknown_or_generic"
    elif a == b:
        state = "same_role_assertion"
    elif (a in web and b in web) or any(a in group and b in group for group in adjacent):
        state = "potentially_overlapping_functions"
    else:
        state = "different_titles_fit_unresolved"
    return dict(version="occupation-relation-diagnostic-v1", state=state, relevance=None, can_infer_negative=False)


def preview(cvs, jobs, cv_groups, jd_groups, protocol, prior_assignments=None):
    require(protocol["mode"] == "known-jd" and protocol["seed_retries"] == 0, "Only fixed-seed known-JD preview allowed")
    require(all(j["decision"] == "keep" and not j["development_only"] and
                j.get("metadata_use_exposure") == "development" and j.get("new_jd_holdout_eligible") is False and
                j.get("label_policy_status") == "requires_expanded_taxonomy_policy" for j in jobs), "JD quality/exposure/label guard missing")
    assignments = assignments_for(cvs + jobs, "known-jd", protocol["seed"], protocol["ratios"])
    if prior_assignments:
        old = {a["record_id"]: a for a in prior_assignments if a["kind"] == "cv"}
        require(set(old) <= {c["record_id"] for c in cvs}, "Lost prior CV identity")
        pinned = {}
        for c in cvs:
            if c["record_id"] in old:
                partition = old[c["record_id"]]["partition"]
                require(partition in PARTITIONS, "Prior development/excluded cohort cannot become prospective")
                require(c["group_id"] not in pinned or pinned[c["group_id"]] == partition, "Merged prior groups cross partitions")
                pinned[c["group_id"]] = partition
        new_groups = {c["group_id"] for c in cvs if c["decision"] == "keep" and not c["development_only"]} - set(pinned)
        new = allocate(new_groups, protocol["seed"], "cv", protocol["ratios"])
        for a in assignments:
            if a["kind"] == "cv" and a["partition"] in PARTITIONS:
                a["partition"] = (pinned | new)[a["group_id"]]
    groups = cv_groups + [dict(g, kind="jd", development_only=False) for g in jd_groups]
    audit = audit_assignments(cvs + jobs, groups, assignments, "known-jd")
    require(audit["leakage_check_passed"], str(audit["errors"]))
    audit.update(independent_real_applicants=False, shared_author=True,
                 qualification="Operational source-bank split only; not independently collected applicants or final-test readiness")
    return assignments, audit


def prepare_intake(metadata_run, catalogue_run, preparation_run, assets, output, prior_intake=None):
    metadata, catalogue, prep, assets = [Path(p).resolve() for p in (metadata_run, catalogue_run, preparation_run, assets)]
    sources = (("metadata", metadata, "jd-metadata-refinement"), ("catalogue", catalogue, "jd-catalogue-expansion"), ("prep", prep, "pretraining-ready"))
    hashes = {}
    for name, path, kind in sources:
        verify(path, kind)
        hashes[name] = file_hash(path / "manifest.json")
    require(read_json(metadata / "summary.json")["source_manifest_sha256"] == hashes["catalogue"], "Catalogue parent mismatch")
    require(read_json(catalogue / "summary.json")["input_manifests"]["preparation"] == hashes["prep"], "Historical CV parent mismatch")
    protected = read_json(metadata / "protected_input_hashes.json")
    require(all(file_hash(ROOT / p) == h for p, h in protected.items()), "Protected inputs changed")
    design, profiles = read_json(assets / "design.json"), read_json(assets / "profiles.json")
    asset_hashes = {name: file_hash(assets / name) for name in ("design.json", "profiles.json", "AUTHORING.md")}
    rendered = admit_profiles(design, profiles)
    for name in design.get("source_files", []):
        require(Path(name).name == name, "Source banks must be local JSON filenames")
        asset_hashes[name] = file_hash(assets / name)
    if design.get("source_files"):
        require(profiles == [p for name in design["source_files"] for p in read_json(assets / name)], "Bank pack differs from authored texts")
    prior = Path(prior_intake).resolve() if prior_intake else None
    if prior:
        check_intake(prior)
        require(not (prior / "prior").exists(), "Chained prior intake requires an explicit multi-generation migration")
        hashes["prior_intake"] = file_hash(prior / "manifest.json")
        require(read_json(prior / "input_receipt.json")["manifests"]["metadata"] == hashes["metadata"], "Prior JD parent differs")
    folder = fresh_folder(output, (metadata, catalogue, prep, assets))
    (folder / "authored").mkdir()
    for name in asset_hashes:
        shutil.copyfile(assets / name, folder / "authored" / name)
    write_csv(folder / "authored/cvs.csv", [r for r, _ in rendered], CV_FIELDS)
    write_json(folder / "authored/evidence.json", [e for _, e in rendered])
    write_json(folder / "protocol.json", design["protocol"])
    spec = deepcopy(read_json(ROOT / "docs/ml/data_configs/new_cvs.template.json")["sources"][0])
    spec.update(path="authored/cvs.csv", namespace=design["version"], version="sha256:" + file_hash(folder / "authored/cvs.csv"),
                collected_at=design["created_on"], usage_terms="Fictional authored profiles; not actual applicants")
    old_config = read_json(prep / "import_config.json")
    history = deepcopy(old_config.get("historical_cv_sources", [])) + [deepcopy(s) for s in old_config["sources"] if s["kind"] == "cv"]
    history_hashes = {}
    for s in history:
        s["path"] = str((prep / s["path"]).resolve())
        history_hashes[s["path"]] = file_hash(s["path"])
    cv_sources = [spec]
    prior_assignments = None
    if prior:
        (folder / "prior").mkdir()
        for name in ("cvs.csv", "evidence.json", "profiles.json", "design.json", "AUTHORING.md"):
            shutil.copyfile(prior / "authored" / name, folder / "prior" / name)
        shutil.copyfile(prior / "cv_dataset/records.jsonl", folder / "prior/records.jsonl")
        shutil.copyfile(prior / "assignments.jsonl", folder / "prior/assignments.jsonl")
        prior_spec = deepcopy(read_json(prior / "cv_import_config.json")["sources"][0])
        prior_spec["path"] = "prior/cvs.csv"
        cv_sources.append(prior_spec)
        prior_assignments = read_lines(folder / "prior/assignments.jsonl")
    config = dict(schema_version=1, dataset_version=design["version"], near_threshold=0.85, sources=cv_sources, historical_cv_sources=history)
    write_json(folder / "cv_import_config.json", config)
    ingest(folder / "cv_import_config.json", folder / "cv_dataset")
    _, cvs, groups = load_dataset(folder / "cv_dataset")
    jobs = read_lines(metadata / "records.jsonl")
    require({j["record_id"] for j in jobs} == set(read_json(catalogue / "catalogue/ids.json")["record_ids"]), "Changed JD catalogue")
    jd_groups = read_json(metadata / "groups.json")
    if prior:
        check_preserved_cv(read_lines(folder / "prior/records.jsonl"), cvs)
    assignments, audit = preview(cvs, jobs, groups, jd_groups, design["protocol"], prior_assignments)
    anchors = [a for a in read_lines(folder / "cv_dataset/protected_anchors.jsonl") if a["kind"] == "cv"]
    lexical = lexical_diagnostics(cvs, anchors)
    write_json(folder / "lexical_diagnostics.json", lexical)
    (folder / "catalogue").mkdir()
    for name in ("records.jsonl", "groups.json", "ids.json", "jd_extraction_evidence.json", "exposure_overlay.json"):
        shutil.copyfile(metadata / name, folder / "catalogue" / name)
    write_lines(folder / "records.jsonl", cvs + jobs)
    write_lines(folder / "assignments.jsonl", assignments)
    write_json(folder / "leakage_report.json", audit)
    by_id = {r["record_id"]: r for r in cvs + jobs}
    distributions = {}
    for p in (*PARTITIONS, "development", "excluded"):
        rows = [by_id[a["record_id"]] for a in assignments if a["kind"] == "cv" and a["partition"] == p]
        distributions[p] = dict(count=len(rows), groups=len({r["group_id"] for r in rows}),
            roles=dict(Counter(r["role"] for r in rows)), banks=dict(Counter(r["lineage"]["source_bank"] for r in rows)),
            experience_kinds=dict(Counter(r["lineage"]["experience_kind"] for r in rows)))
    write_json(folder / "distributions.json", distributions)
    pairs, reasons, shortages = [], [], []
    if audit["partition_ready"]:
        for a in assignments:
            if a["kind"] != "cv" or a["partition"] != "train":
                continue
            cv = by_id[a["record_id"]]
            chosen, missing = choose_mixed(cv, jobs, "train", design["protocol"]["seed"], 10, 3)
            shortages.extend(missing)
            for jid, reason in sorted(chosen.items()):
                jd = by_id[jid]
                pid = "PAIR_" + digest(cv["record_id"] + "|" + jid)[:32]
                pairs.append(dict(pair_id=pid, partition="train", cv_id=cv["record_id"], jd_id=jid,
                    cv_version=cv["normalized_text_sha256"], jd_version=jd["normalized_text_sha256"],
                    cv_text=cv["text_normalized"], jd_text=jd["text_normalized"], label_status="unlabeled",
                    relevance_0_1_2="", cv_evidence="", jd_evidence="", rationale=""))
                reasons.append(dict(pair_id=pid, selection_reason=reason, occupation_relation=occupation_relation(cv["role"], jd["role"])))
    (folder / "train_candidates").mkdir()
    write_csv(folder / "train_candidates/pairs.csv", pairs, PAIR_FIELDS)
    write_json(folder / "train_candidates/selection.json", reasons)
    write_json(folder / "train_candidates/shortages.json", shortages)
    summary = dict(version=VERSION, cv_count=len(cvs), new_cv_count=len(rendered), preserved_cv_count=len(cvs)-len(rendered),
        prior_partitions_preserved=bool(prior), cv_groups=len(groups), declared_banks=len({c["template_group"] for c in cvs}),
        split={p: distributions[p]["count"] for p in PARTITIONS}, cv_development=distributions["development"]["count"],
        cv_excluded=distributions["excluded"]["count"], shared_jd_count=len(jobs), jd_groups=len(jd_groups),
        train_candidate_pairs=len(pairs), sampling_shortages=len(shortages),
        candidate_selection=dict(Counter(r["selection_reason"] for r in reasons)),
        evaluation_pair_workload={p: distributions[p]["count"]*len(jobs) for p in ("validation", "test")},
        labels_created=0, models_trained=0, evaluation_pairs_materialized=False,
        structural_partition_ready=audit["partition_ready"], final_test_ready=False, production_quality_established=False,
        lexical=lexical, source_csv_unchanged=3, pilot_files_unchanged=len(protected)-3,
        limitations=["Individually authored synthetic cohort; one AI author, not independently collected real CVs",
            "Scenario-bank separation does not establish semantic independence; domain confounding remains",
            "No comparison against erased v5 text; historical near checks only cover retained cohorts",
            "Expanded taxonomy label guard remains: same/different title is not a 0/1/2 rubric",
            "Data Analyst remains a research target; no eligible new positive JD coverage has been added"])
    write_json(folder / "summary.json", summary)
    write_json(folder / "input_receipt.json", dict(manifests=hashes, asset_hashes=asset_hashes, historical_cv_hashes=history_hashes))
    shutil.copyfile(metadata / "protected_input_hashes.json", folder / "protected_input_hashes.json")
    for name, path, kind in sources:
        verify(path, kind)
        require(file_hash(path / "manifest.json") == hashes[name], "Historical artifact changed")
    require(all(file_hash(ROOT / p) == h for p, h in protected.items()), "Original CSV/pilot changed")
    require(all(file_hash(p) == h for p, h in history_hashes.items()), "Historical CVs changed")
    require(all(file_hash(assets / p) == h for p, h in asset_hashes.items()), "Authored input changed during admission")
    if prior:
        verify(prior, "authored-cv-intake")
        require(file_hash(prior / "manifest.json") == hashes["prior_intake"], "Prior intake changed")
    seal(folder, "authored-cv-intake", dict(dataset_version=design["version"], input_manifests=hashes, final_test_ready=False))
    return summary


def check_preserved_cv(prior, current):
    """Stable source identity/claims/exposure, independent of new snapshot occurrence paths."""
    by_id = {r["record_id"]: r for r in current}
    fields = ("record_id", "entity_id", "external_id", "namespace", "text_original", "text_normalized", "text_sha256",
              "normalized_text_sha256", "source_group", "template_group", "lineage", "role", "skills", "stack", "experience",
              "is_synthetic", "exposure", "text_scope")
    for old in prior:
        require(old["record_id"] in by_id and all(old[k] == by_id[old["record_id"]][k] for k in fields), "Prior CV identity/lineage changed")


def check_intake(path):
    path = Path(path)
    verify(path, "authored-cv-intake")
    design = read_json(path / "authored/design.json")
    rendered = admit_profiles(design, read_json(path / "authored/profiles.json"))
    require(csv_rows(path / "authored/cvs.csv")[1] == [r for r, _ in rendered], "Authored text/metadata differs from sources")
    require(read_json(path / "authored/evidence.json") == [e for _, e in rendered], "Authored evidence changed")
    _, cvs, groups = load_dataset(path / "cv_dataset")
    source_records = [record(row, spec) for spec in read_json(path / "cv_import_config.json")["sources"]
                      for row in csv_rows(path / spec["path"])[1]]
    require(len(source_records) == len(cvs), "CV count differs from source snapshots")
    check_preserved_cv(source_records, cvs)
    prior_assignments = None
    if (path / "prior").exists():
        prior_rows = admit_profiles(read_json(path / "prior/design.json"), read_json(path / "prior/profiles.json"))
        require(csv_rows(path / "prior/cvs.csv")[1] == [r for r, _ in prior_rows], "Prior source CSV differs")
        require(read_json(path / "prior/evidence.json") == [e for _, e in prior_rows], "Prior evidence differs")
        check_preserved_cv(read_lines(path / "prior/records.jsonl"), cvs)
        prior_assignments = read_lines(path / "prior/assignments.jsonl")
    jobs = read_lines(path / "catalogue/records.jsonl")
    require(read_lines(path / "records.jsonl") == cvs + jobs, "Combined dataset differs from component sources")
    require(read_json(path / "protocol.json") == design["protocol"], "Protocol changed after authoring")
    assignments, audit = preview(cvs, jobs, groups, read_json(path / "catalogue/groups.json"), design["protocol"], prior_assignments)
    require(read_lines(path / "assignments.jsonl") == assignments, "Group split does not reproduce seed/protocol")
    by_id = {r["record_id"]: r for r in cvs + jobs}
    expected = set()
    if audit["partition_ready"]:
        for a in assignments:
            if a["kind"] == "cv" and a["partition"] == "train":
                chosen, _ = choose_mixed(by_id[a["record_id"]], jobs, "train", design["protocol"]["seed"], 10, 3)
                expected.update((a["record_id"], jid) for jid in chosen)
    _, pairs = csv_rows(path / "train_candidates/pairs.csv")
    require(len(pairs) == len(expected) and {(p["cv_id"], p["jd_id"]) for p in pairs} == expected, "Candidate policy or split changed")
    for p in pairs:
        require(p["partition"] == "train" and p["label_status"] == "unlabeled" and p["relevance_0_1_2"] == "", "Unrequested label/holdout mining")
        require(p["cv_text"] == by_id[p["cv_id"]]["text_normalized"] and p["jd_text"] == by_id[p["jd_id"]]["text_normalized"] and
                p["cv_version"] == digest(p["cv_text"]) and p["jd_version"] == digest(p["jd_text"]), "Pair text/hash mismatch")
    return dict(verified=True, structural_partition_ready=audit["partition_ready"], final_test_ready=False,
                cv_count=len(cvs), jd_count=len(jobs), train_candidates=len(pairs))
