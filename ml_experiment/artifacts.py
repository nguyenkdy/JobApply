"""Environment receipts and checked local model artifacts."""
import importlib.metadata
from pathlib import Path
import platform
import shutil

from ml_data.common import ROOT, file_hash, read_json, require, seal, verify, write_json

DEPENDENCIES = ("numpy", "scipy", "scikit-learn", "joblib", "torch", "transformers",
                "sentence-transformers", "huggingface-hub", "tokenizers", "safetensors")


def environment():
    return dict(python=platform.python_version(), platform=platform.platform(),
                dependencies={name: importlib.metadata.version(name) for name in DEPENDENCIES})


def snapshot_code(folder):
    runtime = folder / "runtime_source"
    runtime.mkdir()
    for package in ("ml_experiment", "ml_data"):
        target = runtime / package
        target.mkdir()
        for source in sorted((ROOT / package).glob("*.py")):
            shutil.copyfile(source, target / source.name)
    target = runtime / "jobapply_pilot_v1"
    target.mkdir()
    for name in ("run_bm25.py", "baseline_common.py", "compare_embeddings.py"):
        shutil.copyfile(ROOT / "jobapply_pilot_v1" / name, target / name)


def seal_experiment(folder, kind, metadata):
    snapshot_code(folder)
    return seal(folder, kind, metadata)


def load_bundle(folder):
    """Verify all bytes before loading a locally generated pickle; never untrusted artifacts."""
    import joblib
    folder = Path(folder)
    verify(folder, "step4-model")
    env = read_json(folder / "environment.json")
    require(env["dependencies"] == environment()["dependencies"], "Model environment differs from locked versions")
    chosen = read_json(folder / "selected.json")
    estimator = joblib.load(folder / "model.joblib") if chosen["family"] in {"text", "metadata", "combined"} else None
    if estimator is not None:
        from .core import FEATURE_SETS
        require(chosen["features"] == list(FEATURE_SETS[chosen["family"]]), "Model feature schema mismatch")
        require(estimator.n_features_in_ == len(chosen["features"]), "Model input dimension mismatch")
        require(list(estimator.classes_) == [0, 1, 2], "Model classes differ")
    return chosen, estimator


def package_model(folder, selected, estimator, jobs, jd_vectors, encoder_folder, encoder_lock, prep, selection_hash):
    import joblib
    import numpy as np
    folder.mkdir()
    write_json(folder / "selected.json", selected)
    write_json(folder / "environment.json", environment())
    write_json(folder / "catalogue.json", jobs)
    np.save(folder / "jd_vectors.npy", jd_vectors, allow_pickle=False)
    shutil.copyfile(encoder_lock, folder / "encoder.lock.json")
    for name in read_json(encoder_lock)["files"]:
        target = folder / "encoder" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(encoder_folder) / name, target)
    if estimator is not None:
        joblib.dump(estimator, folder / "model.joblib", compress=3)
    write_json(folder / "usage.json", dict(scope="Offline synthetic proxy benchmark, known 50-JD catalogue only",
        encoder_location="encoder", fit_partition="train", selected_on="validation", refit_after_selection=False,
        input_preparation_manifest_sha256=file_hash(prep / "manifest.json"), selection_sha256=selection_hash,
        inference_inputs="Professional text and explicit scoped metadata, never personal metadata or labels",
        production_ready=False, no_automatic_hiring_decisions=True))
    seal_experiment(folder, "step4-model", dict(selected=selected["name"], selection_sha256=selection_hash))
