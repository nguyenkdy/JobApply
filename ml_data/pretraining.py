"""Prepare complete proxy-label experiment inputs; never score or train models."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import shutil

from .annotation import LABELER_VERSION, label_pairs_by_evidence, validate_labels
from .jd_integrity import assert_frozen_jd_identity_and_exposure
from .cohort import export_cohort
from .common import (csv_rows, file_hash, fresh_folder, read_json, read_lines, require,
                     seal, verify, write_csv, write_json)
from .expansion import CV_COLUMNS, protected_inputs, workload_and_distribution
from .extraction import EXTRACTOR_VERSION, enrich_upstream_jds
from .ingest import ingest
from .sampling import sample_pairs
from .splitting import PARTITIONS, audit_split, make_split


def check_conditions(folder, sealed=True):
    folder = Path(folder)
    if sealed:
        verify(folder, "pretraining-ready")
    audit = audit_split(folder / "dataset", folder / "split")
    records = read_lines(folder / "dataset/records.jsonl")
    assignments = read_lines(folder / "split/assignments.jsonl")
    by_id = {r["record_id"]: r for r in records}
    old = [r for r in records if r["kind"] == "cv" and r["namespace"] == "jobapply-synthetic-careers-v2"]
    new = [r for r in records if r["kind"] == "cv" and r["namespace"] == "independent-careers-v3"]
    catalogue = read_json(folder / "split/eval_catalogue.json")
    cat_ids = set(catalogue["record_ids"])
    checks = dict(structural_partition_ready=audit["partition_ready"], leakage=audit["leakage_check_passed"],
                  old_sixty_all_development=len(old) == 60 and all(r["development_only"] and r["exposure"] == "development" for r in old),
                  sixty_new_kept=len(new) == 60 and all(r["decision"] == "keep" and not r["development_only"] for r in new),
                  twelve_new_groups=len({r["group_id"] for r in new}) == 12,
                  catalogue_fifty=len(cat_ids) == 50)
    counts, class_counts = {}, {}
    for partition in PARTITIONS:
        cv_ids = {a["record_id"] for a in assignments if a["kind"] == "cv" and a["partition"] == partition}
        cvs = [by_id[rid] for rid in cv_ids]
        checks[partition + "_five_roles"] = len({r["role"] for r in cvs}) == 5
        checks[partition + "_five_experience_kinds"] = len({r["lineage"]["experience_kind"] for r in cvs}) == 5
        checks[partition + "_multiple_families"] = len({r["group_id"] for r in cvs}) >= 2
        pairs, labels = folder / (partition + "_pairs"), folder / (partition + "_labels")
        pm, lm = verify(pairs, "pairs"), verify(labels, "automatic-labels")
        require(pm["dataset_manifest_sha256"] == file_hash(folder / "dataset/manifest.json"), "Pairs from another dataset")
        require(pm["split_manifest_sha256"] == file_hash(folder / "split/manifest.json"), "Pairs from another split")
        require(lm["source_pairs_manifest_sha256"] == file_hash(pairs / "manifest.json"), "Labels from another pair source")
        require(lm["dataset_manifest_sha256"] == file_hash(folder / "dataset/manifest.json"), "Labels from another dataset")
        validation = validate_labels(pairs / "pairs.csv", labels / "pairs.csv")
        _, rows = csv_rows(labels / "pairs.csv")
        actual_grid = {(r["cv_id"], r["jd_id"]) for r in rows}
        checks[partition + "_full_catalogue_grid"] = actual_grid == {(c, j) for c in cv_ids for j in cat_ids} and len(actual_grid) == len(rows)
        checks[partition + "_numeric_label_coverage"] = validation["complete"]
        for row in rows:
            require(row["partition"] == partition, "Wrong pair partition")
            require(row["cv_version"] == by_id[row["cv_id"]]["normalized_text_sha256"]
                    and row["jd_version"] == by_id[row["jd_id"]]["normalized_text_sha256"], "Pair/document version mismatch")
        counts[partition] = len(rows)
        class_counts[partition] = validation["relevance_counts"]
    checks["train_has_three_classes"] = set(class_counts["train"]) == {"0", "1", "2"}
    return dict(ready_for_automatic_label_experiment=all(checks.values()), checks=checks,
        blockers=[key for key, passed in checks.items() if not passed], pair_counts=counts,
        class_counts=class_counts, human_review_required=False, model_training_performed=False,
        final_test_evaluated=False, production_quality_established=False,
        interpretation="Technical prerequisites for a synthetic automatic-proxy-label experiment only")


def prepare_experiment(upstream, audited, reference, prior_batch, assets, output):
    upstream, audited, reference, prior_batch, assets = [Path(p).resolve() for p in (upstream, audited, reference, prior_batch, assets)]
    for folder, kind in ((upstream, "upstream"), (audited, "benchmark-audit"), (reference, "benchmark-prep"), (prior_batch, "synthetic-cvs")):
        verify(folder, kind)
    before = protected_inputs(upstream)
    original_runs = {str(p): file_hash(p / "manifest.json") for p in (upstream, audited, reference, prior_batch)}
    asset_hashes = {name: file_hash(assets / name) for name in ("design.json", "profiles.json")}
    folder = fresh_folder(output, (upstream, audited, reference, prior_batch, assets))
    design = read_json(assets / "design.json")
    write_json(folder / "protocol.json", dict(design["protocol"],
        design_sha256=asset_hashes["design.json"], profiles_sha256=asset_hashes["profiles.json"],
        labeler_version=LABELER_VERSION, extractor_version=EXTRACTOR_VERSION,
        rule_files={p.name: file_hash(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
        seed_retries=0, cv_label_targeting=False, old_cohort_policy="development with historical template ancestry",
        metrics_plan=dict(k=5, recall_relevance_thresholds=[1, 2], ndcg_gain="2^label-1",
                          aggregation="macro by CV; report zero-positive queries separately",
                          rule_baseline_and_text_metadata_ablations_required=True)))
    extraction = enrich_upstream_jds(upstream, folder / "jd_extraction")
    cohort = export_cohort(assets, folder / "new_cv_batch")
    columns, old_rows = csv_rows(audited / "cv_batch/cvs.csv")
    for row in old_rows:
        row["exposure"] = "development"
        lineage = json.loads(row["lineage_json"])
        lineage["exposure_history"] = [dict(exposure="development", reason="user-authorized retirement of invalid v2 benchmark", date="2026-11-14",
                                             audit_manifest_sha256=file_hash(audited / "manifest.json"))]
        row["lineage_json"] = json.dumps(lineage, ensure_ascii=False, sort_keys=True)
    write_csv(folder / "old_cv_development.csv", old_rows, columns)
    shutil.copyfile(audited / "cv_batch/cvs.csv", folder / "old_cv_original_snapshot.csv")
    write_json(folder / "exposure_registry.json", dict(source_groups=sorted(row["source_group"] for row in old_rows),
        exposure="development", applies_to="all existing/future variants of these sources and connected templates"))
    config = deepcopy(read_json(upstream / "import_config.json"))
    config["dataset_version"] = "pretraining-independent-v3-" + asset_hashes["profiles.json"][:12]
    for item in config["context_files"]:
        item["path"] = str(upstream / item["path"])
    config["sources"][0].update(path="jd_extraction/canonical_jd_enriched.csv",
                               version="sha256:" + file_hash(folder / "jd_extraction/canonical_jd_enriched.csv"))
    config["sources"][0]["columns"].update(role="extracted_role", skills="extracted_skills", stack="extracted_stack", experience="extracted_experience_json")
    for path, namespace in (("old_cv_development.csv", "jobapply-synthetic-careers-v2"), ("new_cv_batch/cvs.csv", "independent-careers-v3")):
        config["sources"].append(dict(path=path, kind="cv", namespace=namespace,
            version="sha256:" + file_hash(folder / path), columns=CV_COLUMNS, source_url=None, collected_at=None,
            usage_terms="Fictional task-authored profiles; never real applicant data"))
    config["historical_cv_sources"] = [dict(path=str(prior_batch / "cvs.csv"), kind="cv", namespace="protected-original-v1",
                                           version="sha256:" + file_hash(prior_batch / "manifest.json"), columns=CV_COLUMNS)]
    for path, role in (("jd_extraction/jd_extraction_evidence.json", "jd_metadata_evidence"),
                       ("new_cv_batch/evidence.json", "synthetic_cv_assertion_evidence"),
                       ("new_cv_batch/design.json", "prospective_authoring_design"),
                       ("new_cv_batch/profiles.json", "new_career_sources"),
                       ("old_cv_original_snapshot.csv", "unmodified_legacy_cv_source"),
                       ("exposure_registry.json", "development_exposure_registry"),
                       ("protocol.json", "frozen_pretraining_protocol")):
        config["context_files"].append(dict(path=path, role=role))
    write_json(folder / "import_config.json", config)
    imported = ingest(folder / "import_config.json", folder / "dataset")
    records = read_lines(folder / "dataset/records.jsonl")
    frozen = assert_frozen_jd_identity_and_exposure(read_lines(upstream / "dataset/records.jsonl"), records)
    make_split(folder / "dataset", folder / "split", mode="known-jd", seed=design["protocol"]["seed"],
               ratios=tuple(design["protocol"]["ratios"]), frozen_catalogue=reference / "split/eval_catalogue.json")
    plan = workload_and_distribution(records, read_lines(folder / "split/assignments.jsonl"), design["protocol"]["seed"])
    catalogue_size = len(read_json(folder / "split/eval_catalogue.json")["record_ids"])
    for distribution in plan["distributions"].values():
        distribution["jd_available_shared"] = distribution["jd_catalogue_count"]
        distribution["jd_catalogue_count"] = catalogue_size
    for partition in PARTITIONS:
        sample_pairs(folder / "dataset", folder / "split", folder / (partition + "_pairs"), partition=partition,
                     strategy="census", seed=design["protocol"]["seed"], evaluation_catalogue_only=True)
        label_pairs_by_evidence(folder / "dataset", folder / (partition + "_pairs"), folder / "jd_extraction",
                                folder / (partition + "_labels"))
    sampling = sample_pairs(folder / "dataset", folder / "split", folder / "train_sampling_diagnostic", partition="train",
                            strategy="mixed", seed=design["protocol"]["seed"], positive_per_cv=2, evaluation_catalogue_only=True)
    conditions = check_conditions(folder, sealed=False)
    write_json(folder / "readiness.json", conditions)
    # Preserve missing labels as real blockers; never force numerical targets.
    new_ids = {r["record_id"] for r in records if r["namespace"] == "independent-careers-v3"}
    edges = [e for e in read_lines(folder / "dataset/group_edges.jsonl") if e["left"] in new_ids or e["right"] in new_ids]
    groups = read_json(folder / "dataset/groups.json")
    catalog_ids = set(read_json(folder / "split/eval_catalogue.json")["record_ids"])
    jobs = [r for r in records if r["record_id"] in catalog_ids]
    evidence = {e["job_id"]: e for e in read_json(folder / "jd_extraction/jd_extraction_evidence.json")}
    report = dict(version="pretraining-handoff-v1", date="2026-11-14", readiness=conditions,
        cohort=cohort, import_summary=imported, frozen_jd=frozen,
        distributions=plan["distributions"], extraction=extraction,
        catalogue=dict(count=len(jobs), original_50_ids_unchanged=True, by_role=dict(Counter(r["role"] for r in jobs)),
                       missing_metadata={f: sum(not r[f] for r in jobs) for f in ("role", "skills", "stack", "experience")},
                       requirement_operators=dict(Counter(c["operator"] for j in jobs for c in evidence[j["external_id"]]["requirement_clauses"]))),
        lineage=dict(new_groups=len({r["group_id"] for r in records if r["record_id"] in new_ids}),
                     new_group_sizes=[len(g["record_ids"]) for g in groups if set(g["record_ids"]) & new_ids],
                     new_cv_edge_reasons=dict(Counter(e["reason"] for e in edges)),
                     historical_v1_reference_count=len(csv_rows(prior_batch / "cvs.csv")[1]), old_v2_development_count=len(old_rows)),
        sampling_diagnostic=sampling,
        input_manifests=original_runs, data_analyst=read_json(upstream / "summary.json")["data_analyst_accounting"],
        stop_boundary="Before Step 4: no BM25/embedding scores, model training, model selection or test metrics",
        limitations=["One synthetic AI author cohort; disjoint framework groups are not independent real applicants",
                     "Automatic proxy labels measure consistency with a declared rubric, not true job suitability",
                     "Level 2 is strong role/stack/scoped-duration signal; not proof all mandatory clauses are met",
                     "AND/OR/mixed-clause evidence is retained; unresolved logic is not silently converted to AND",
                     "50 selected JD subset only; no claim for 788-JD retrieval or unseen JD generalization",
                     "Metadata-derived labels and features share assumptions; compare rule baseline and ablations in Step 4"])
    require(before == protected_inputs(upstream), "Original source or pilot changed")
    for path, expected in original_runs.items():
        verify(path)
        require(file_hash(Path(path) / "manifest.json") == expected, "Historical run changed")
    require(all(file_hash(assets / name) == expected for name, expected in asset_hashes.items()), "CV assets changed during run")
    report["preservation"] = dict(source_csv_unchanged=3, pilot_files_unchanged=len(before)-3, historical_runs_unchanged=len(original_runs))
    write_json(folder / "protected_input_hashes.json", before)
    write_json(folder / "handoff_report.json", report)
    seal(folder, "pretraining-ready", dict(ready=conditions["ready_for_automatic_label_experiment"], stopped_before_step4=True))
    return conditions
