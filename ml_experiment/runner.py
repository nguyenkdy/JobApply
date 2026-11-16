"""Frozen protocol: train/validation selection is persisted before test scoring."""
from copy import deepcopy
import importlib.metadata
from pathlib import Path
import shutil
import time

import joblib
import numpy as np

from ml_data.common import (csv_rows, file_hash, fresh_folder, read_json, read_lines,
                            require, verify, write_csv, write_json)
from ml_data.label_rules import label_pair_row
from ml_data.pretraining import check_conditions
from .artifacts import environment, load_bundle, package_model, seal_experiment
from .core import (C_VALUES, FEATURE_SETS, evaluate, expected_relevance, fit_classifier,
                   metadata_features, professional_view, select_validation, selection_key)
from .text import encode, lexical_index, load_encoder


def protocol():
    return dict(version="step4-v1", seed=20261113, catalogue="frozen 50 IDs", ranking_k=5,
        fit="train only; no refit on validation", tuning_partition="validation", test_policy="after persisted selection only",
        candidates=["keyword", "bm25", "e5", "lr_text", "lr_metadata", "lr_combined"], c_grid=list(C_VALUES),
        class_weight="balanced", solver="lbfgs", max_iter=3000, tolerance=1e-8,
        features={k: list(v) for k, v in FEATURE_SETS.items()},
        selection="max macro NDCG@5; tie macro Recall@5(label>=2); then simpler family and smaller C; metrics rounded 12 decimals",
        complexity_order=["keyword", "bm25", "e5", "metadata", "text", "combined"],
        rule_baseline="diagnostic only, excluded from selection because it defines target labels",
        test_methods="keyword, BM25, E5, rule diagnostic and best validation C per LR family; no post-test selection",
        undefined_metrics="null; report defined/undefined CV counts; do not drop rows from ranking catalogue",
        label_target="automatic_rule_proxy, not independent gold", relevance_thresholds=[1, 2], ndcg_gain="2^label-1",
        text=dict(query_prefix="query: ", passage_prefix="passage: ", max_tokens=512, batch_size=4,
                  pooling="token-weighted normalized chunk mean, L2 normalized", torch_threads=2,
                  deterministic_algorithms=True, bm25_k1=1.5, bm25_b=0.75, score_ties="JD record ID lexical"),
        fairness_scope="structured personal metadata excluded by allowlist; no free-form CV/PDF or population fairness claim",
        deployment="offline package only; no API/UI/VM changes")


def partition_pairs(prep, partition, cv_ids, job_ids):
    _, rows = csv_rows(prep / (partition + "_labels") / "pairs.csv")
    require({(r["cv_id"], r["jd_id"]) for r in rows} == {(c, j) for c in cv_ids for j in job_ids}
            and len(rows) == len(cv_ids)*len(job_ids), "Pair grid differs from fixed catalogue")
    require(all(r["partition"] == partition and r["label_status"] == "labeled"
                and r["relevance_0_1_2"] in {"0", "1", "2"} for r in rows), "Unresolved/wrong partition labels")
    return sorted(rows, key=lambda r: (r["cv_id"], r["jd_id"]))


def build_features(pairs, records, jobs, lexical, cv_vectors, jd_vectors, receipts):
    indices = {j["record_id"]: i for i, j in enumerate(jobs)}
    lexical_scores = {cv_id: lexical.score(professional_view(records[cv_id])["text"]) for cv_id in {r["cv_id"] for r in pairs}}
    rows, rules = [], []
    for pair in pairs:
        cv, jd = records[pair["cv_id"]], records[pair["jd_id"]]
        ji = indices[pair["jd_id"]]
        lex = lexical_scores[pair["cv_id"]][ji]
        metadata = metadata_features(cv, jd, receipts[jd["external_id"]])
        rows.append(dict(cv_id=pair["cv_id"], jd_id=pair["jd_id"], keyword=float(lex["keyword_overlap_count"]),
                         bm25=float(lex["bm25_score"]), e5=float(cv_vectors[pair["cv_id"]] @ jd_vectors[ji]), **metadata))
        # Recompute from documents/metadata; never pass the target label to the rule.
        rule = label_pair_row(dict(cv_text=cv["text_normalized"], jd_text=jd["text_normalized"]), cv, jd, receipts[jd["external_id"]])
        require(rule["relevance_0_1_2"] in {"0", "1", "2"}, "Rule diagnostic abstained; inspect frozen rubric")
        rules.append(float(rule["relevance_0_1_2"]))
    return rows, np.asarray(rules)


def score_method(candidate, models, rows, rules):
    if candidate["family"] == "rule_proxy":
        return rules
    if candidate["family"] in {"keyword", "bm25", "e5"}:
        return np.asarray([r[candidate["family"]] for r in rows])
    return expected_relevance(models[candidate["name"]], rows, candidate["features"])


def train_select(train_rows, train_labels, validation_rows, validation_labels, validation_rules, records):
    models, candidates = {}, []
    for complexity, method in enumerate(("keyword", "bm25", "e5")):
        candidates.append(dict(name=method, family=method, complexity=complexity, features=[]))
    for family, complexity in (("metadata", 3), ("text", 4), ("combined", 5)):
        for c in C_VALUES:
            name = f"lr_{family}_C{c:g}"
            features = list(FEATURE_SETS[family])
            models[name] = fit_classifier(train_rows, train_labels, features, c)
            candidates.append(dict(name=name, family=family, complexity=complexity, features=features, c=c))
    candidates.append(dict(name="rule_proxy", family="rule_proxy", features=[], complexity=99))
    for candidate in candidates:
        scores = score_method(candidate, models, validation_rows, validation_rules)
        candidate["metrics"] = evaluate(validation_rows, validation_labels, scores, records)
    selected = select_validation(candidates)
    family_winners = {family: min([c for c in candidates if c["family"] == family], key=selection_key)["name"]
                      for family in FEATURE_SETS}
    return models, candidates, selected, family_winners


def diagnostics(rows, labels, scores):
    by_cv = {}
    for i, row in enumerate(rows):
        by_cv.setdefault(row["cv_id"], []).append(i)
    top = [i for ids in by_cv.values() for i in sorted(ids, key=lambda i: (-float(scores[i]), rows[i]["jd_id"]))[:5]]
    return dict(top5_slots=len(top), label_zero_in_top5=sum(labels[i] == 0 for i in top),
        different_role_in_top5=sum(not rows[i]["role_equal"] for i in top),
        same_role_disjoint_stack_in_top5=sum(rows[i]["role_equal"] and rows[i]["stack_known"] and not rows[i]["stack_coverage"] for i in top),
        partial_or_unknown_experience_in_top5=sum(rows[i]["experience_coverage"] < 1 for i in top),
        observed_experience_gap_in_top5=sum(rows[i]["experience_gap_years"] > 0 or rows[i]["strict_bound_violation"] for i in top),
        interpretation="Overlapping diagnostics, not expert error labels; unknown experience is not rejection")


def personal_metadata_probe(pairs, records, jobs, index, cv_vectors, jd_vectors, receipts, candidates, models):
    base_rows, base_rules = build_features(pairs, records, jobs, index, cv_vectors, jd_vectors, receipts)
    variations = [dict(name="Fictional A", age=22, gender="woman", address="Fictional location A"),
                  dict(name="Fictional B", age=58, gender="man", address="Fictional location B"),
                  dict(name="", age=None, gender="unspecified", address="")]
    results = []
    for personal in variations:
        altered = deepcopy(records)
        for cv_id in cv_vectors:
            altered[cv_id].update(personal)
            require(professional_view(altered[cv_id]) == professional_view(records[cv_id]), "Personal fields entered projection")
        rows, rules = build_features(pairs, altered, jobs, index, cv_vectors, jd_vectors, receipts)
        require(rows == base_rows, "Personal metadata changed feature rows")
        for candidate in candidates:
            a = score_method(candidate, models, base_rows, base_rules)
            b = score_method(candidate, models, rows, rules)
            delta = float(np.max(np.abs(a-b)))
            require(delta == 0, "Personal metadata changed scores")
            results.append(dict(method=candidate["name"], variant=len(results)//len(candidates), max_score_delta=delta,
                                same_top5=True))
    return dict(cv_count=len({r["cv_id"] for r in pairs}), variants_per_cv=len(variations),
        checks=results, passed=True, scope="Structured allowlist with identical professional text; cached identical E5 inputs",
        limitations="Does not test embedded PII in free-form text/PDF, proxy discrimination or demographic outcome fairness")


def run(preparation, encoder_folder, encoder_lock, output):
    started = time.perf_counter()
    prep, encoder_folder, encoder_lock = (Path(p).resolve() for p in (preparation, encoder_folder, encoder_lock))
    ready = check_conditions(prep)
    require(ready["ready_for_automatic_label_experiment"], "Preparation conditions failed")
    before = file_hash(prep / "manifest.json")
    protected = read_json(prep / "protected_input_hashes.json")
    from ml_data.common import ROOT
    require(all(file_hash(ROOT / p) == h for p, h in protected.items()), "Original inputs changed")
    folder = fresh_folder(output, (prep, encoder_folder))
    print("Writing immutable protocol before scoring", flush=True)
    write_json(folder / "protocol.json", protocol())
    write_json(folder / "environment.json", environment())
    installed = sorted(f"{d.metadata['Name']}=={d.version}" for d in importlib.metadata.distributions())
    (folder / "requirements.lock.txt").write_text("\n".join(installed)+"\n", encoding="utf-8")
    shutil.copyfile(encoder_lock, folder / "encoder.lock.json")
    write_json(folder / "input_receipt.json", dict(preparation=str(prep), manifest_sha256=before,
        dataset_manifest_sha256=file_hash(prep / "dataset/manifest.json"),
        split_manifest_sha256=file_hash(prep / "split/manifest.json"), checks=ready["checks"]))
    all_records = {r["record_id"]: r for r in read_lines(prep / "dataset/records.jsonl")}
    assignments = read_lines(prep / "split/assignments.jsonl")
    cv_ids = {p: sorted(a["record_id"] for a in assignments if a["kind"] == "cv" and a["partition"] == p)
              for p in ("train", "validation", "test")}
    job_ids = sorted(read_json(prep / "split/eval_catalogue.json")["record_ids"])
    jobs = [all_records[r] for r in job_ids]
    records = {rid: all_records[rid] for rid in job_ids + sum(cv_ids.values(), [])}
    write_json(folder / "documents.json", records)
    receipts = {r["job_id"]: r for r in read_json(prep / "jd_extraction/jd_extraction_evidence.json")}
    snapshots = folder / "inputs"
    snapshots.mkdir()
    timings = {}
    model = load_encoder(encoder_folder, encoder_lock)
    jd_vectors, timings["encode_jd"] = encode(model, jobs, "passage: ")
    np.save(folder / "jd_vectors.npy", jd_vectors, allow_pickle=False)
    index = lexical_index(jobs)
    matrices, labels, rules_by_part, vectors, pairs_by_part = {}, {}, {}, {}, {}
    for partition in ("train", "validation"):
        print("Scoring " + partition + " (test is not scored yet)", flush=True)
        pairs = partition_pairs(prep, partition, cv_ids[partition], job_ids)
        pairs_by_part[partition] = pairs
        shutil.copyfile(prep / (partition + "_labels") / "pairs.csv", snapshots / (partition + "_labels.csv"))
        cv_records = [records[c] for c in cv_ids[partition]]
        matrix, timings["encode_" + partition] = encode(model, cv_records, "query: ")
        np.save(folder / (partition + "_cv_vectors.npy"), matrix, allow_pickle=False)
        vectors.update(zip(cv_ids[partition], matrix))
        rows, rules = build_features(pairs, records, jobs, index, vectors, jd_vectors, receipts)
        matrices[partition], rules_by_part[partition] = rows, rules
        labels[partition] = [int(p["relevance_0_1_2"]) for p in pairs]
        write_csv(folder / (partition + "_features.csv"), rows, tuple(rows[0]))
    t = time.perf_counter()
    models, candidates, selected, family_winners = train_select(matrices["train"], labels["train"], matrices["validation"],
        labels["validation"], rules_by_part["validation"], records)
    timings["fit_and_select_seconds"] = time.perf_counter()-t
    train_ids_hash = file_hash(snapshots / "train_labels.csv")
    model_dir = folder / "fitted_models"
    model_dir.mkdir()
    for name, estimator in models.items():
        joblib.dump(estimator, model_dir / (name + ".joblib"), compress=3)
    write_json(folder / "validation.json", candidates)
    chosen = {k: v for k, v in selected.items() if k != "metrics"}
    selection = dict(selected=chosen, family_winners=family_winners,
        validation_metrics=selected["metrics"]["macro"], training_labels_sha256=train_ids_hash,
        validation_sha256=file_hash(folder / "validation.json"), protocol_sha256=file_hash(folder / "protocol.json"),
        fitted_model_hashes={p.name: file_hash(p) for p in sorted(model_dir.glob("*.joblib"))},
        test_scores_seen=False, test_metrics_seen=False, refit_on_validation=False)
    write_json(folder / "selection.json", selection)
    selection_hash = file_hash(folder / "selection.json")
    print("Selection frozen: " + chosen["name"] + "; entering single test stage", flush=True)
    # Test documents/labels have only undergone structural preparation checks until here.
    partition = "test"
    test_pairs = partition_pairs(prep, partition, cv_ids[partition], job_ids)
    shutil.copyfile(prep / "test_labels/pairs.csv", snapshots / "test_labels.csv")
    matrix, timings["encode_test"] = encode(model, [records[c] for c in cv_ids["test"]], "query: ")
    np.save(folder / "test_cv_vectors.npy", matrix, allow_pickle=False)
    vectors.update(zip(cv_ids["test"], matrix))
    test_rows, test_rules = build_features(test_pairs, records, jobs, index, vectors, jd_vectors, receipts)
    test_labels = [int(p["relevance_0_1_2"]) for p in test_pairs]
    write_csv(folder / "test_features.csv", test_rows, tuple(test_rows[0]))
    methods = [c for c in candidates if c["family"] not in FEATURE_SETS or c["name"] in family_winners.values()]
    test_results, prediction_rows = {}, []
    for candidate in methods:
        scores = score_method(candidate, models, test_rows, test_rules)
        test_results[candidate["name"]] = evaluate(test_rows, test_labels, scores, records)
        test_results[candidate["name"]]["diagnostics"] = diagnostics(test_rows, test_labels, scores)
        prediction_rows.extend(dict(method=candidate["name"], cv_id=r["cv_id"], jd_id=r["jd_id"], score=float(score),
                                    relevance=y) for r, score, y in zip(test_rows, scores, test_labels))
    write_json(folder / "test.json", test_results)
    write_csv(folder / "test_predictions.csv", prediction_rows, tuple(prediction_rows[0]))
    validation_predictions = [dict(method=c["name"], cv_id=r["cv_id"], jd_id=r["jd_id"], score=float(s), relevance=y)
        for c in candidates for r, s, y in zip(matrices["validation"], score_method(c, models, matrices["validation"], rules_by_part["validation"]), labels["validation"])]
    write_csv(folder / "validation_predictions.csv", validation_predictions, tuple(validation_predictions[0]))
    print("Checking deterministic encoding and structured privacy invariance", flush=True)
    probe_ids = cv_ids["train"][:2]
    probe_vectors, timings["repeat_train_probe"] = encode(model, [records[c] for c in probe_ids], "query: ")
    delta = float(np.max(np.abs(probe_vectors - np.stack([vectors[c] for c in probe_ids]))))
    require(delta <= 1e-6, "Encoder repeat differs beyond tolerance")
    privacy_pairs = [p for p in pairs_by_part["train"] if p["cv_id"] in probe_ids]
    privacy = personal_metadata_probe(privacy_pairs, records, jobs, index, vectors, jd_vectors, receipts, methods, models)
    write_json(folder / "privacy_probe.json", privacy)
    t = time.perf_counter()
    package_model(folder / "model_package", chosen, models.get(chosen["name"]), jobs, jd_vectors,
                  encoder_folder, encoder_lock, prep, selection_hash)
    reloaded, estimator = load_bundle(folder / "model_package")
    reference_scores = score_method(selected, models, matrices["validation"], rules_by_part["validation"])
    loaded_models = {chosen["name"]: estimator} if estimator is not None else {}
    reloaded_scores = score_method(reloaded, loaded_models, matrices["validation"], rules_by_part["validation"])
    require(np.array_equal(reference_scores, reloaded_scores), "Serialized model changes predictions")
    timings["package_seconds"] = time.perf_counter()-t
    require(file_hash(folder / "selection.json") == selection_hash, "Selection modified after test")
    require(all(file_hash(model_dir / n) == h for n, h in selection["fitted_model_hashes"].items()), "Model refit after selection")
    verify(prep, "pretraining-ready")
    require(file_hash(prep / "manifest.json") == before, "Preparation changed")
    require(all(file_hash(ROOT / p) == h for p, h in protected.items()), "Source/pilot changed")
    timings["total_seconds"] = time.perf_counter()-started
    summary = dict(selected=chosen, validation=selected["metrics"]["macro"], test=test_results[chosen["name"]]["macro"],
        validation_comparison={c["name"]: c["metrics"]["macro"] for c in candidates},
        test_comparison={name: r["macro"] for name, r in test_results.items()},
        counts=dict(cv={p: len(ids) for p, ids in cv_ids.items()}, jd=len(jobs), pairs=dict(train=len(matrices["train"]), validation=len(matrices["validation"]), test=len(test_rows))),
        family_winners=family_winners, encoder_repeat_max_abs_delta=delta, package_reload_identical=True,
        selection_sha256=selection_hash, input_preparation_sha256=before, timings=timings,
        source_csv_unchanged=3, pilot_files_unchanged=len(protected)-3, preparation_unchanged=True,
        privacy_probe_passed=privacy["passed"], test_selection_used=False, refit_after_selection=False,
        limitations=["Synthetic single-author cohort; automatic rule labels, not gold or real-applicant validation",
                     "Rule baseline defines targets; metadata model may reproduce rule rather than learn suitability",
                     "15 validation/test CVs in only 3 template families each; model selection is uncertain",
                     "9 validation and 9 test CVs have no label-2 positive; strict recall uses only 6 queries per partition",
                     "Known 50-JD catalogue only, not 788-JD retrieval or unseen JD generalization",
                     "Data Analyst pending usable non-development JD; excluded from this five-role experiment only",
                     "Structured privacy probe is not an end-to-end PDF or population fairness audit"])
    write_json(folder / "summary.json", summary)
    seal_experiment(folder, "step4-experiment", dict(preparation_manifest_sha256=before, selection_sha256=selection_hash,
                                                   selected=chosen["name"], test_evaluated=True, production_ready=False))
    print("Completed experiment: " + str(folder), flush=True)
    return summary
