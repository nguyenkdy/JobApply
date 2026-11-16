"""Publish complete offline inference inputs without changing fit or test results."""
import argparse
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml_data.common import file_hash, fresh_folder, read_json, require, verify, write_json
from ml_experiment.artifacts import seal_experiment
from ml_experiment.predict import predict_records


def release(run, output, verification_output):
    run = Path(run).resolve()
    verify(run, "step4-experiment")
    prep = Path(read_json(run / "input_receipt.json")["preparation"])
    verify(prep, "pretraining-ready")
    require(file_hash(prep / "manifest.json") == read_json(run / "input_receipt.json")["manifest_sha256"], "Wrong preparation source")
    source = run / "model_package"
    manifest = verify(source, "step4-model")
    target = fresh_folder(output, (run, prep))
    for name in manifest["artifacts"]:
        if name.startswith(("tool_source/", "runtime_source/")):
            continue
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, path)
    job_ids = {j["external_id"] for j in read_json(target / "catalogue.json")}
    write_json(target / "jd_receipts.json", {r["job_id"]: r for r in read_json(prep / "jd_extraction/jd_extraction_evidence.json") if r["job_id"] in job_ids})
    shutil.copyfile(run / "requirements.lock.txt", target / "requirements.lock.txt")
    write_json(target / "release.json", dict(experiment_manifest_sha256=file_hash(run / "manifest.json"),
        original_package_manifest_sha256=file_hash(source / "manifest.json"), selection_sha256=file_hash(run / "selection.json"),
        purpose="Add JD scope evidence and full environment lock for self-contained offline inference; no refit or reselection"))
    seal_experiment(target, "step4-model", dict(selected=manifest["selected"], selection_sha256=manifest["selection_sha256"]))
    # Reproduce two validation queries through packaged inference, never tune on test.
    selection = read_json(run / "selection.json")
    docs = read_json(run / "documents.json")
    candidate = next(c for c in read_json(run / "validation.json") if c["name"] == selection["selected"]["name"])
    ids = [r["cv_id"] for r in candidate["metrics"]["by_cv"][:2]]
    predictions = predict_records(target, [docs[i] for i in ids])
    expected = {r["cv_id"]: r["top5"] for r in candidate["metrics"]["by_cv"]}
    require(all([j["jd_id"] for j in r["ranking"][:5]] == expected[r["cv_id"]] for r in predictions), "Packaged Top5 differs from validation")
    from ml_data.common import csv_rows
    scores = {(r["cv_id"], r["jd_id"]): float(r["score"]) for r in csv_rows(run / "validation_predictions.csv")[1]
              if r["method"] == selection["selected"]["name"] and r["cv_id"] in ids}
    delta = max(abs(j["score"]-scores[r["cv_id"], j["jd_id"]]) for r in predictions for j in r["ranking"])
    require(delta <= 1e-6, "Packaged score mismatch")
    check = fresh_folder(verification_output, (run, prep, target))
    write_json(check / "verification.json", dict(package_manifest_sha256=file_hash(target / "manifest.json"),
        validation_cv_count=len(ids), same_top5=True, max_score_delta=delta, tolerance=1e-6, no_refit=True, no_test_reselection=True))
    print(target)
    print(check / "verification.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verification-output", type=Path, required=True)
    args = parser.parse_args()
    release(args.run, args.output, args.verification_output)
