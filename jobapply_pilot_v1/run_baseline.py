"""Milestone 0: snapshot, validate and reproduce the AI-draft development baseline."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import platform
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

from baseline_common import (catalog, complete_grid, finite, keyed_rows, macro_metrics,
                             metrics, new_run_path, read_csv, sha256, validate_k,
                             validate_ranks, write_json, write_table)

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SCOPE = "development/regression only; AI draft labels; shared JD catalogue; no human gold or model selection"
LOCK = "requirements-ml-win-py314.lock.txt"


def git(*args):
    return subprocess.check_output(["git", "-C", str(REPO), *args])


def file_info(path):
    data = path.read_bytes()
    info = dict(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
    if path.suffix in {".csv", ".json", ".txt", ".md", ".py", ".js", ".jsx", ".css", ".yaml", ".sh"}:
        info.update(utf8_bom=data.startswith(b"\xef\xbb\xbf"),
                    crlf=data.count(b"\r\n"), lf_without_cr=data.count(b"\n") - data.count(b"\r\n"))
    return info


def verify_run(folder):
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    for relative, expected in manifest["artifacts"].items():
        path = (folder / relative).resolve()
        if not path.is_relative_to(folder.resolve()) or sha256(path) != expected["sha256"]:
            raise ValueError(f"Artifact integrity failure: {relative}")
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}
    if actual != set(manifest["artifacts"]) | {"manifest.json"}:
        raise ValueError("Run contains missing or unmanifested files")
    return manifest


def normalize_labels(source, template, target, cvs, jobs):
    rows = read_csv(source, ("cv_id", "job_id", "relevance_0_1_2", "rationale"), allow_legacy_blank=True)
    fields = list(rows[0])
    old_schema = ["cv_id", "job_id", "relevance_0_1_2", "", "rationale"]
    template_rows = read_csv(template)
    if fields != old_schema or list(template_rows[0]) != ["cv_id", "job_id", "relevance_0_1_2", "reviewer", "rationale"]:
        raise ValueError("Unexpected legacy schema; inspect provenance before migration")
    if any(r[""] for r in rows):
        raise ValueError("Unnamed field has values; do not infer their meaning")
    cv_versions = {r["cv_id"]: hashlib.sha256(r["cv_text"].encode()).hexdigest() for r in cvs}
    job_versions = {r["job_id"]: hashlib.sha256(r["match_text"].encode()).hexdigest() for r in jobs}
    seen, normalized = set(), []
    for row in rows:
        key = row["cv_id"], row["job_id"]
        if key in seen or key[0] not in cv_versions or key[1] not in job_versions:
            raise ValueError(f"Duplicate or unknown label pair {key}")
        seen.add(key)
        if row["relevance_0_1_2"] not in {"0", "1", "2"}:
            raise ValueError(f"Invalid legacy label {key}")
        normalized.append(dict(cv_id=key[0], job_id=key[1], relevance_0_1_2=row["relevance_0_1_2"],
                               reviewer="", rationale=row["rationale"], annotation_origin="ai_draft",
                               label_status="needs_review", cv_version=cv_versions[key[0]],
                               job_version=job_versions[key[1]]))
    complete_grid(seen, cv_versions, job_versions)
    write_table(target, normalized)
    return dict(source_sha256=sha256(source), derived_sha256=sha256(target),
                action="Reconstruct empty reviewer field using template and run_bm25.py schema; preserve every ID, grade and rationale",
                original_header=fields, derived_header=list(normalized[0]),
                evidence="results/judgments_template.csv and run_bm25.py; README documents AI origin",
                unknown="Original missing header identity and historical label checksum remain unproven",
                review="All reviewer values remain empty; specialist review of labels AND experience scopes is required",
                version_hash_rule="SHA256 of UTF-8 professional text after CSV universal-newline decoding",
                label_counts=dict(Counter(r["relevance_0_1_2"] for r in rows)))


def audit_history(inputs):
    old = json.loads((inputs / "results/experience_v2/run_info.json").read_text())
    mapping = {"score_file_sha256": "results/embedding_vs_bm25.csv", "label_file_sha256": "judgments_ai_draft.csv",
               "job_notes_sha256": "jobapply_experience_v2/jd_experience.csv",
               "cv_notes_sha256": "jobapply_experience_v2/cv_experience.csv"}
    checks = {}
    for key, name in mapping.items():
        path = inputs / name
        content = path.read_bytes().decode("utf-8-sig").replace("\r\n", "\n")
        variants = {}
        for bom in (False, True):
            for newline, label in (("\n", "LF"), ("\r\n", "CRLF")):
                data = (b"\xef\xbb\xbf" if bom else b"") + content.replace("\n", newline).encode()
                variants[f"{'BOM' if bom else 'no_BOM'}_{label}"] = hashlib.sha256(data).hexdigest() == old[key]
        blob = git("show", "HEAD:jobapply_pilot_v1/" + name)
        checks[name] = dict(recorded_sha256=old[key], working_copy=file_info(path),
                            byte_match=sha256(path) == old[key], newline_variant_matches=variants,
                            git_blob_sha256=hashlib.sha256(blob).hexdigest(),
                            git_blob_matches=hashlib.sha256(blob).hexdigest() == old[key])
    backup = "results/embedding_vs_bm25_backup_20261110_163750.csv"
    bad = []
    for row in read_csv(inputs / backup):
        try:
            finite(row["bm25_score"], "backup")
        except ValueError:
            bad.append(dict(cv_id=row["cv_id"], job_id=row["job_id"], value=row["bm25_score"]))
    return dict(historical_checksums=checks, excluded_from_model_inputs=[backup],
                backup_invalid_bm25_count=len(bad), backup_invalid_examples=bad[:3],
                unresolved=["Historical label checksum cannot be recovered by BOM/newline changes",
                            "Upstream source/clean/matching CSVs and cleaning scripts are absent",
                            "AI relevance and experience annotations require independent specialist review"])


def compare_tables(actual_path, reference_path, columns, tolerance=1e-6):
    actual, reference = keyed_rows(actual_path, columns), keyed_rows(reference_path, columns)
    if actual.keys() != reference.keys():
        raise ValueError(f"Pair mismatch comparing {actual_path} with {reference_path}")
    differences = {}
    for column in columns:
        deltas = [abs(finite(actual[key][column], column) - finite(reference[key][column], column)) for key in actual]
        differences[column] = dict(max_absolute_delta=max(deltas),
                                   tolerance=0 if column.startswith("rank_") else tolerance,
                                   mismatches=sum(d > (0 if column.startswith("rank_") else tolerance)
                                                  and not (not column.startswith("rank_") and math.isclose(d, tolerance, rel_tol=1e-9))
                                                  for d in deltas))
    return differences


def compare_metrics(actual, reference_path, k):
    reference = read_csv(reference_path, ("cv_id", "method", f"recall_at_{k}", f"ndcg_at_{k}"))
    lookup = {(r["cv_id"], r["method"]): r for r in actual}
    checks = []
    for row in reference:
        method = "base_classifier" if row["method"] == "classifier" else row["method"]
        observed = lookup[row["cv_id"], method]
        for column in (f"recall_at_{k}", f"ndcg_at_{k}"):
            expected = finite(row[column], column) if row[column] else None
            value = observed[column]
            equal = value is None and expected is None
            if value is not None and expected is not None:
                equal = math.isclose(value, expected, abs_tol=1e-12, rel_tol=0)
            checks.append(equal)
    return dict(values_compared=len(checks), mismatches=checks.count(False), absolute_tolerance=1e-12)


def environment(lock):
    installed = {d.metadata["Name"].lower().replace("_", "-"): d.version for d in importlib.metadata.distributions()}
    expected = dict(line.split("==") for line in lock.read_text().splitlines() if line and not line.startswith("#"))
    mismatches = {name: dict(expected=version, actual=installed.get(name.lower().replace("_", "-")))
                  for name, version in expected.items() if installed.get(name.lower().replace("_", "-")) != version}
    check = subprocess.run([sys.executable, "-m", "pip", "check"], capture_output=True, text=True)
    if mismatches or check.returncode:
        raise ValueError(f"ML lock/pip check failed: {mismatches}; {check.stdout} {check.stderr}")
    if platform.python_version() != "3.14.3" or platform.system() != "Windows" or platform.machine() != "AMD64":
        raise ValueError("This measured lock targets CPython 3.14.3 Windows AMD64; validate a separate lock for other platforms")
    return dict(python=sys.version, executable=sys.executable, platform=platform.platform(),
                installed=installed, pip_check=check.stdout.strip(), lock_sha256=sha256(lock))


def execute(args, out):
    from compare_embeddings import encoder_snapshot, generate
    from train_matcher import train, training_rows
    from jobapply_experience_v2.run_experiment import main as experience_run
    from run_bm25 import run
    from threadpoolctl import threadpool_limits

    inputs, source = out / "inputs", out / "source"
    inputs.mkdir()
    source.mkdir()
    tracked = git("ls-files", "-z").decode().split("\0")
    original_hashes = {}
    inventory = {}
    for relative in filter(None, tracked):
        path = REPO / relative
        inventory[relative] = file_info(path)
        if relative.startswith("jobapply_pilot_v1/") and path.suffix in {".csv", ".json", ".joblib", ".txt"}:
            # Lock is code/config, not historical data.
            if path.name in {LOCK, "encoder.lock.json"} or "/results/reruns/" in relative:
                continue
            target = inputs / path.relative_to(HERE)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            original_hashes[relative] = sha256(path)
    source_hashes = {}
    for path in sorted([*HERE.glob("*.py"), *HERE.joinpath("jobapply_experience_v2").glob("*.py"),
                        HERE / LOCK, HERE / "encoder.lock.json"]):
        target = source / path.relative_to(HERE)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        source_hashes[path] = sha256(path)
    test_source = REPO / "tests/ml/test_baseline.py"
    shutil.copyfile(test_source, source / "test_baseline.py")
    source_hashes[test_source] = sha256(test_source)
    write_json(out / "repository_inventory.json", inventory)
    write_json(out / "environment.json", environment(source / LOCK))
    jobs = catalog(inputs / "jobs_pilot.csv", "job_id", "match_text")
    cvs = catalog(inputs / "cvs_synthetic.csv", "cv_id", "cv_text")
    selected = read_csv(inputs / "selection_manifest.csv", ("job_id", "pilot_group", "selection_reason"))
    if len(selected) != len(jobs) or {r["job_id"] for r in selected} != {r["job_id"] for r in jobs}:
        raise ValueError("Selection manifest IDs disagree with the job catalogue")
    if len({r["content_group_id"] for r in jobs}) != len(jobs):
        raise ValueError("Duplicate content_group_id in pilot catalogue")
    selected_by_id = {r["job_id"]: r for r in selected}
    for job in jobs:
        if any(job[c] != selected_by_id[job["job_id"]][c] for c in ("pilot_group", "selection_reason")):
            raise ValueError("Selection metadata drift")
        sections = [("Chức danh", job["title_for_matching"]), ("Nhiệm vụ", job["tasks_text"]),
                    ("Yêu cầu", job["requirements_text"]), ("Ưu tiên / Nice to have", job["preferred_requirements_text"])]
        if job["match_text"] != "\n\n".join(label + ":\n" + text for label, text in sections if text):
            raise ValueError(f"match_text differs from source sections: {job['job_id']}")
    for cv in cvs:
        if (inputs / "synthetic_cv_texts" / (cv["cv_id"] + ".txt")).read_text(encoding="utf-8-sig") != cv["cv_text"]:
            raise ValueError(f"CSV/TXT CV text mismatch: {cv['cv_id']}")
    validate_k(args.k, len(jobs))
    label_path = out / "labels_ai_draft.normalized.csv"
    migration = normalize_labels(inputs / "judgments_ai_draft.csv", inputs / "results/judgments_template.csv", label_path, cvs, jobs)
    write_json(out / "label_schema_migration.json", migration)
    labels = keyed_rows(label_path, ["relevance_0_1_2"])
    historical_scores = keyed_rows(inputs / "results/embedding_vs_bm25.csv")
    complete_grid(historical_scores, [r["cv_id"] for r in cvs], [r["job_id"] for r in jobs])
    training_rows(historical_scores, labels)
    for name in ("results/supervised/training_pairs.csv", "results/experience_v2/experience_pairs.csv",
                 "results/supervised/held_out_predictions.csv", "results/experience_v2/held_out_predictions.csv"):
        previous = keyed_rows(inputs / name, ("relevance", "bm25_score", "cosine"))
        if previous.keys() != labels.keys():
            raise ValueError(f"Historical pair mismatch: {name}")
        for key in labels:
            if int(previous[key]["relevance"]) != int(labels[key]["relevance_0_1_2"]):
                raise ValueError(f"Historical grade mismatch: {name}/{key}")
            if any(finite(previous[key][c], c) != finite(historical_scores[key][c], c) for c in ("bm25_score", "cosine")):
                raise ValueError(f"Historical feature mismatch: {name}/{key}")
    audit = audit_history(inputs)
    audit["historical_label_and_feature_values_match"] = True
    audit["catalog_checks"] = "selection IDs/metadata, unique content groups, JD section assembly, CV CSV/TXT text all match"
    audit["data_counts"] = dict(cvs=len(cvs), jobs=len(jobs), pairs=len(labels),
                                 job_groups=dict(Counter(r["pilot_group"] for r in jobs)),
                                 sites=dict(Counter(r["site"] for r in jobs)))
    write_json(out / "audit.json", audit)
    baseline, top = run(jobs, cvs, args.k)
    write_table(out / "rankings_all.csv", baseline)
    write_table(out / "top_matches.csv", top, list(baseline[0]))
    # Run from professional text, never infer provenance of the historical cosine file.
    print("Encoding professional text with pinned E5 revision", flush=True)
    rows, encoder = generate(jobs, cvs, baseline, local_files_only=not args.allow_download)
    write_table(out / "embedding_vs_bm25.csv", rows)
    # Record bytes of the actual cached encoder files, not just a moving branch name.
    snapshot, _ = encoder_snapshot(local_files_only=True)
    encoder["files"] = {p.relative_to(snapshot).as_posix(): file_info(p) for p in sorted(snapshot.rglob("*")) if p.is_file()}
    write_json(out / "encoder.json", encoder)
    scores = keyed_rows(out / "embedding_vs_bm25.csv")
    prepared = training_rows(scores, labels)
    with threadpool_limits(limits=1):
        train(prepared, out / "supervised", args.k)
        _, evaluations = experience_run(SimpleNamespace(pilot=inputs, notes=inputs / "jobapply_experience_v2",
                                                        labels=label_path, scores=out / "embedding_vs_bm25.csv",
                                                        k=args.k, output=out / "experience_v2", lexical_check=False))
    keyword_pairs = keyed_rows(out / "rankings_all.csv")
    validate_ranks(keyword_pairs, "rank_keyword", "keyword_overlap_count")
    for cv in sorted({r["cv_id"] for r in cvs}):
        ordered = sorted([dict(r, relevance=int(labels[r["cv_id"], r["job_id"]]["relevance_0_1_2"]))
                          for r in baseline if r["cv_id"] == cv], key=lambda r: r["rank_keyword"])
        evaluations.append(dict(cv_id=cv, method="keyword", **metrics(ordered, args.k)))
    write_table(out / "metrics_by_cv.csv", evaluations)
    summary = [dict(method=name, **macro_metrics([r for r in evaluations if r["method"] == name], args.k))
               for name in sorted({r["method"] for r in evaluations})]
    write_table(out / "macro_metrics.csv", summary)
    regression = {
        "historical_scores": compare_tables(out / "embedding_vs_bm25.csv", inputs / "results/embedding_vs_bm25.csv",
                                             ["bm25_score", "cosine", "rank_bm25", "rank_embedding"]),
        "historical_bm25": compare_tables(out / "rankings_all.csv", inputs / "results/rankings_all.csv",
                                           ["bm25_score", "rank_bm25", "rank_keyword"]),
        "historical_supervised": compare_tables(out / "supervised/held_out_predictions.csv",
                                                 inputs / "results/supervised/held_out_predictions.csv",
                                                 ["match_score", "rank_classifier"]),
        "historical_experience": compare_tables(out / "experience_v2/held_out_predictions.csv",
                                                 inputs / "results/experience_v2/held_out_predictions.csv",
                                                 ["score_base_classifier", "score_coverage_control", "score_experience_classifier",
                                                  "rank_base_classifier", "rank_coverage_control", "rank_experience_classifier"])}
    if args.k == 5:
        regression["historical_metrics"] = {
            name: compare_metrics(evaluations, inputs / f"results/{name}/metrics_by_cv.csv", args.k)
            for name in ("supervised", "experience_v2")}
    regression["historical_ranks_unchanged"] = all(
        value["mismatches"] == 0 for group in ("historical_scores", "historical_bm25", "historical_supervised", "historical_experience")
        for column, value in regression[group].items() if column.startswith("rank_"))
    if args.compare_run:
        reference = args.compare_run.resolve()
        previous_manifest = verify_run(reference)
        if previous_manifest["config"]["k"] != args.k:
            raise ValueError("Cannot compare runs with different k")
        files = ["labels_ai_draft.normalized.csv", "embedding_vs_bm25.csv", "rankings_all.csv", "metrics_by_cv.csv", "macro_metrics.csv",
                 "supervised/held_out_predictions.csv", "experience_v2/held_out_predictions.csv"]
        regression["repeat_run"] = dict(reference=str(reference),
                                        equal_bytes={name: sha256(out / name) == sha256(reference / name) for name in files})
        if not all(regression["repeat_run"]["equal_bytes"].values()):
            raise ValueError("Repeated run differs; inspect artifacts before claiming reproducibility")
    write_json(out / "regression.json", regression)
    if any(sha256(REPO / name) != checksum for name, checksum in original_hashes.items()):
        raise ValueError("Original artifact changed during run")
    if any(sha256(path) != checksum for path, checksum in source_hashes.items()):
        raise ValueError("ML code/config/tests changed during run; rerun using a stable source snapshot")
    config = dict(k=args.k, scope=SCOPE, cv_count=len(cvs), job_count=len(jobs), pair_count=len(labels),
                  split="leave-one-CV-out; sorted cv_id/job_id; shared JD catalogue",
                  split_manifest={cv: {"held_out_cv": cv, "train_cvs": sorted(r["cv_id"] for r in cvs if r["cv_id"] != cv)}
                                  for cv in sorted(r["cv_id"] for r in cvs)},
                  gain="2**label - 1", relevant_label=2, undefined_metric="null; excluded from macro with counts",
                  bm25=dict(k1=1.5, b=0.75, query_terms="unique", tie_break="job_id ascending"),
                  classifier=dict(C=1.0, solver="lbfgs", max_iter=2000, scaler="train fold only", threads=1),
                  features={"base_classifier": ["bm25_score", "cosine"],
                            "coverage_control": ["bm25_score", "cosine", "coverage"],
                            "experience_classifier": ["bm25_score", "cosine", "coverage", "gap_years_input"]},
                  input_allowlist=["inputs/jobs_pilot.csv", "inputs/cvs_synthetic.csv", "labels_ai_draft.normalized.csv",
                                   "inputs/jobapply_experience_v2/cv_experience.csv", "inputs/jobapply_experience_v2/jd_experience.csv"],
                  historical_scores_use="comparison only; fresh scores generated from text",
                  original_artifacts_unchanged=True, output_encoding="UTF-8 without BOM, LF; input snapshot byte-preserved")
    write_json(out / "config.json", config)
    import joblib
    provenance = dict(scope=SCOPE, config_sha256=sha256(out / "config.json"),
                      labels_sha256=sha256(label_path), scores_sha256=sha256(out / "embedding_vs_bm25.csv"),
                      encoder_sha256=sha256(out / "encoder.json"), environment_sha256=sha256(out / "environment.json"),
                      code={p.relative_to(source).as_posix(): sha256(p) for p in source.rglob("*") if p.is_file()})
    # Only load artifacts this process just trained, never historical joblib files.
    for name in ("supervised/match_classifier.joblib", "experience_v2/experience_classifier.joblib"):
        bundle = joblib.load(out / name)
        bundle["provenance"] = provenance
        joblib.dump(bundle, out / name)
    write_json(out / "manifest.json", dict(status="complete", scope=SCOPE, config=config,
               created_at_utc=datetime.now(timezone.utc).isoformat(), git_commit=git("rev-parse", "HEAD").decode().strip(),
               git_branch=git("branch", "--show-current").decode().strip(),
               code_state="source snapshot hashes describe working code, including uncommitted changes",
               command=sys.argv, artifacts={p.relative_to(out).as_posix(): file_info(p)
                                            for p in sorted(out.rglob("*")) if p.is_file()}))
    verify_run(out)
    print(json.dumps(summary, indent=2))
    print("Completed:", out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--allow-download", action="store_true", help="Allow fetching the pinned encoder if not cached")
    parser.add_argument("--compare-run", type=Path)
    parser.add_argument("--verify-run", type=Path, help="Verify all artifact hashes without executing ML")
    args = parser.parse_args()
    if args.verify_run:
        verify_run(args.verify_run.resolve())
        print("Verified:", args.verify_run)
        return
    out = (args.output or new_run_path(HERE, "baseline")).resolve()
    # An existing directory is never reusable, including an incomplete failed run.
    out.mkdir(parents=True, exist_ok=False)
    try:
        execute(args, out)
    except Exception as exc:
        write_json(out / "failure.json", dict(status="failed", error=f"{type(exc).__name__}: {exc}", scope=SCOPE))
        raise


if __name__ == "__main__":
    main()
