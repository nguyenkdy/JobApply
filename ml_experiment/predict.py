"""Offline inference from a checked release and explicit professional CV metadata."""
import argparse
from pathlib import Path
import math
import os

import numpy as np

from ml_data.common import fresh_folder, read_json, require, write_json
from .artifacts import load_bundle
from .core import expected_relevance, metadata_features
from .text import encode, lexical_index, load_encoder


def validate_cv(cv):
    require(cv.get("text_scope") == "professional" and isinstance(cv.get("text_normalized"), str)
            and len(cv["text_normalized"].strip()) >= 80, "Supply professional text, not a raw CV/PDF")
    require(isinstance(cv.get("role", ""), str), "Invalid role")
    for field in ("skills", "stack"):
        require(isinstance(cv.get(field, []), list) and all(isinstance(s, str) for s in cv.get(field, [])), "Invalid " + field)
    require(isinstance(cv.get("experience", {}), dict), "Experience must be an explicit scoped dictionary")
    require(all(isinstance(k, str) and type(v) in (float, int) and math.isfinite(v) and v >= 0
                for k, v in cv.get("experience", {}).items()), "Invalid months; unknown must be omitted")
    require(cv.get("lineage", {}).get("experience_kind", "unknown") in {"employment", "contract", "project", "internship", "unknown"},
            "Invalid experience kind")


def predict_records(package, cvs):
    package = Path(package)
    selected, estimator = load_bundle(package)
    require((package / "jd_receipts.json").is_file(), "Use the complete inference release with JD evidence")
    for cv in cvs:
        validate_cv(cv)
    jobs = read_json(package / "catalogue.json")
    receipts = read_json(package / "jd_receipts.json")
    index = lexical_index(jobs)
    vectors = None
    if selected["family"] in {"e5", "text", "combined"}:
        encoder = load_encoder(package / "encoder", package / "encoder.lock.json")
        vectors, _ = encode(encoder, cvs, "query: ")
    jd_vectors = np.load(package / "jd_vectors.npy", allow_pickle=False)
    require(len(jd_vectors) == len(jobs), "Catalogue/vector mismatch")
    result = []
    for ci, cv in enumerate(cvs):
        lexical = index.score(cv["text_normalized"])
        features = [dict(bm25=float(lexical[ji]["bm25_score"]), e5=float(vectors[ci] @ jd_vectors[ji]) if vectors is not None else 0,
                         keyword=float(lexical[ji]["keyword_overlap_count"]),
                         **metadata_features(cv, jd, receipts[jd["external_id"]])) for ji, jd in enumerate(jobs)]
        if estimator is None:
            scores = [f[selected["family"]] for f in features]
        else:
            scores = expected_relevance(estimator, features, selected["features"])
        ordered = sorted(range(len(jobs)), key=lambda j: (-float(scores[j]), jobs[j]["record_id"]))
        result.append(dict(cv_id=cv.get("record_id", "provided-cv"), model=selected["name"],
            ranking=[dict(rank=rank, jd_id=jobs[j]["record_id"], job_id=jobs[j]["external_id"], score=float(scores[j])) for rank, j in enumerate(ordered, 1)]))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--cv-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    results = predict_records(args.package, [read_json(args.cv_json)])
    output = fresh_folder(args.output, (args.package, args.cv_json))
    write_json(output / "top5.json", [dict(r, ranking=r["ranking"][:5]) for r in results])
    print(output / "top5.json")
