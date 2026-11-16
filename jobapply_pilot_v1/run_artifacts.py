"""Validate completed local baseline runs before loading their trusted model bundles."""
import ast
import json
from pathlib import Path

from baseline_common import catalog, sha256
from run_baseline import environment, verify_run

HERE = Path(__file__).resolve().parent


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def verified_manifest(run_dir):
    run_dir = Path(run_dir).resolve()
    manifest = verify_run(run_dir)
    if manifest.get("status") != "complete":
        raise ValueError("Run must have status=complete")
    return run_dir, manifest


def definitions(path, names):
    """Compare preprocessing semantics across snapshots without executing snapshot code."""
    result = {}
    for node in ast.parse(path.read_text(encoding="utf-8-sig")).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            keys = [node.name]
        elif isinstance(node, ast.Assign):
            keys = [t.id for t in node.targets if isinstance(t, ast.Name)]
        else:
            keys = []
        for key in set(keys) & set(names):
            # Docstrings/comments do not affect the feature algorithm.
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.body and isinstance(node.body[0], ast.Expr):
                if isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                    node.body = node.body[1:]
            result[key] = ast.dump(node, include_attributes=False)
    if set(result) != set(names):
        raise ValueError(f"Unsupported preprocessing definitions: {path}")
    return result


def load_experience_run(run_dir):
    import joblib
    import numpy as np
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    from jobapply_experience_v2.run_experiment import EXPERIENCE_FEATURES, experience_inputs

    folder, manifest = verified_manifest(run_dir)
    required = ["config.json", "environment.json", "encoder.json", "labels_ai_draft.normalized.csv",
                "embedding_vs_bm25.csv", "experience_v2/experience_classifier.joblib",
                "source/encoder.lock.json", "source/requirements-ml-win-py314.lock.txt",
                "inputs/jobs_pilot.csv", "inputs/cvs_synthetic.csv",
                "inputs/jobapply_experience_v2/jd_experience.csv", "inputs/jobapply_experience_v2/cv_experience.csv"]
    if not set(required).issubset(manifest["artifacts"]):
        raise ValueError("Run manifest lacks required inference artifacts")
    config = read_json(folder / "config.json")
    if manifest.get("config") != config or config.get("k") != 5:
        raise ValueError("Run config mismatch or unsupported ranking cutoff (Top 5 required)")
    if config.get("features", {}).get("experience_classifier") != list(EXPERIENCE_FEATURES):
        raise ValueError("Unsupported feature order in run config")
    if config.get("bm25") != dict(k1=1.5, b=0.75, query_terms="unique", tie_break="job_id ascending"):
        raise ValueError("Unsupported BM25 configuration")
    env = environment(folder / "source/requirements-ml-win-py314.lock.txt")
    recorded_env = read_json(folder / "environment.json")
    if recorded_env["python"] != env["python"] or recorded_env["lock_sha256"] != env["lock_sha256"]:
        raise ValueError("Run environment is incompatible")
    checks = {
        "run_bm25.py": ["STOP_WORDS", "ALIASES", "TOKEN", "tokenize", "BM25", "run"],
        "compare_embeddings.py": ["MODEL", "REVISION", "split_for_model", "encode_texts", "compare"],
        "jobapply_experience_v2/run_experiment.py": ["gap_features", "experience_inputs"],
    }
    for relative, names in checks.items():
        if "source/" + relative not in manifest["artifacts"]:
            raise ValueError(f"Missing source compatibility snapshot: {relative}")
        if definitions(folder / "source" / relative, names) != definitions(HERE / relative, names):
            raise ValueError(f"Preprocessing incompatible with selected run: {relative}")
    encoder = read_json(folder / "encoder.json")
    lock = read_json(folder / "source/encoder.lock.json")
    expected = dict(model=lock["model"], revision=lock["revision"], max_seq_length=lock["max_seq_length"],
                    device="cpu", query_prefix="query: ", passage_prefix="passage: ", batch_size=4,
                    pooling="normalized chunks; token-weighted mean; L2 normalization", torch_threads=1,
                    seed=0, deterministic_algorithms=True, score_decimals=6)
    if any(encoder.get(k) != v for k, v in expected.items()):
        raise ValueError("Unsupported encoder/preprocessing configuration")
    if not lock.get("files") or any(encoder.get("files", {}).get(k, {}).get("sha256") != v["sha256"]
                                    for k, v in lock["files"].items()):
        raise ValueError("Run encoder and encoder lock disagree")
    jobs = catalog(folder / "inputs/jobs_pilot.csv", "job_id", "match_text")
    cvs = catalog(folder / "inputs/cvs_synthetic.csv", "cv_id", "cv_text")
    if (len(jobs), len(cvs)) != (config["job_count"], config["cv_count"]):
        raise ValueError("Run catalogue counts disagree")
    requirements, experience = experience_inputs(folder / "inputs", folder / "inputs/jobapply_experience_v2")
    # User-selected local project run, integrity/environment checked before deserialization.
    bundle = joblib.load(folder / "experience_v2/experience_classifier.joblib")
    if bundle.get("mode") != "full" or bundle.get("version") != 2 or tuple(bundle.get("features", ())) != EXPERIENCE_FEATURES:
        raise ValueError("Unsupported model mode/version/feature order")
    provenance = bundle.get("provenance", {})
    for key, name in {"config_sha256": "config.json", "labels_sha256": "labels_ai_draft.normalized.csv",
                      "scores_sha256": "embedding_vs_bm25.csv", "encoder_sha256": "encoder.json",
                      "environment_sha256": "environment.json"}.items():
        if provenance.get(key) != sha256(folder / name):
            raise ValueError(f"Model provenance mismatch: {key}")
    code = {name.removeprefix("source/"): info["sha256"] for name, info in manifest["artifacts"].items()
            if name.startswith("source/")}
    if provenance.get("code") != code:
        raise ValueError("Model source provenance mismatch")
    model = bundle.get("pipeline")
    if not isinstance(model, Pipeline) or [type(step) for _, step in model.steps] != [StandardScaler, LogisticRegression]:
        raise ValueError("Unsupported model pipeline")
    if model.n_features_in_ != len(EXPERIENCE_FEATURES) or list(model.classes_) != [0, 1, 2]:
        raise ValueError("Model feature dimensions/classes mismatch")
    if not all(np.isfinite(v).all() for v in (model[0].mean_, model[0].scale_, model[1].coef_, model[1].intercept_)):
        raise ValueError("Non-finite model parameters")
    return dict(folder=folder, manifest=manifest, bundle=bundle, jobs=jobs, cvs=cvs,
                requirements=requirements, experience=experience)
