"""Display five recommendations for an anonymized professional CV in the pilot catalogue."""
import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np

from run_experiment import HERE, gap_features, read_csv


def recommend(args):
    pilot = args.pilot.resolve()
    sys.path.insert(0, str(pilot))
    from run_bm25 import BM25

    jobs = read_csv(pilot / "jobs_pilot.csv")
    cvs = {c["cv_id"]: c for c in read_csv(pilot / "cvs_synthetic.csv")}
    if args.cv_id:
        cv = cvs[args.cv_id]
        text = cv["cv_text"]
        months = {r["scope"]: int(r["months"]) for r in read_csv(HERE / "cv_experience.csv")
                  if r["cv_id"] == args.cv_id}
    else:
        text = args.cv_text.read_text(encoding="utf-8-sig").strip()
        months = json.loads(args.months.read_text(encoding="utf-8-sig")) if args.months else {}
    if not text.strip() or not isinstance(months, dict) or any(type(v) is not int or v<0 for v in months.values()):
        raise ValueError("Supply professional CV text and non-negative integer months by scope.")
    from run_experiment import experience_inputs
    requirements, _ = experience_inputs(pilot)
    mode = "lexical" if args.lexical_check else "full"
    out = pilot / "results" / ("experience_lexical_control" if args.lexical_check else "experience_v2")
    bundle = joblib.load(out / "experience_classifier.joblib")
    if bundle["mode"] != mode:
        raise ValueError("Run the corresponding experience experiment before the demo.")
    docs = [r["match_text"] for r in jobs]
    cosine = None
    if mode == "full":
        from compare_embeddings import MODEL, REVISION, encode_texts
        from sentence_transformers import SentenceTransformer

        encoder = SentenceTransformer(MODEL, revision=REVISION, device="cpu", local_files_only=True)
        vectors, _ = encode_texts(encoder, docs, "passage: ")
        query, _ = encode_texts(encoder, [text], "query: ")
        cosine = vectors @ query[0]
    lexical = BM25(docs).score(text)
    items = []
    for i, job in enumerate(jobs):
        feature = gap_features(requirements[job["job_id"]], months)
        feature["bm25_score"] = lexical[i]["bm25_score"]
        if cosine is not None:
            feature["cosine"] = cosine[i]
        items.append(feature)
    x = np.asarray([[r[k] for k in bundle["features"]] for r in items])
    model = bundle["pipeline"]
    predicted = model.predict_proba(x) @ model.classes_
    order = sorted(range(len(jobs)), key=lambda i:(-predicted[i],jobs[i]["job_id"]))
    from baseline_common import validate_k
    validate_k(args.k, len(jobs))
    for rank,i in enumerate(order[:args.k],1):
        gap = items[i]["gap_months_observed"]
        print(f"{rank}. {jobs[i]['title_for_matching']} | {jobs[i]['job_id']} | "
              f"score={predicted[i]:.3f}/2 | documented gap (months)={gap if gap is not None else 'unknown'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pilot", type=Path, default=Path.cwd())
    ap.add_argument("--lexical-check", action="store_true")
    ap.add_argument("--k", type=int, default=5)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--cv-id")
    group.add_argument("--cv-text", type=Path)
    ap.add_argument("--months",type=Path, help="Optional JSON mapping role/skill scopes to documented months for a new CV.")
    try:
        recommend(ap.parse_args())
    except (OSError, ValueError, KeyError) as exc:
        sys.exit(f"Demo error: {exc}")
