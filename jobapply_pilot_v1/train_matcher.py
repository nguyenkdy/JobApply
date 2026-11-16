"""Train and evaluate a two-feature CV-JD classifier on the JobApply pilot."""
import argparse
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from baseline_common import (complete_grid, finite, keyed_rows as read_by_pair,
                             macro_metrics, metrics, new_run_path, validate_k,
                             validate_ranks, write_table)


FEATURES = ("bm25_score", "cosine")


def training_rows(scores, judgments):
    if scores.keys() != judgments.keys():
        raise ValueError("The score and label files must contain exactly the same CV-JD pairs.")
    complete_grid(scores)
    validate_ranks(scores, "rank_bm25", "bm25_score")
    validate_ranks(scores, "rank_embedding", "cosine")
    rows = []
    for (cv, job), score in sorted(scores.items()):
        grade = judgments[cv, job]["relevance_0_1_2"].strip()
        if grade not in {"0", "1", "2"}:
            raise ValueError(f"Invalid grade at {cv}/{job}: {grade!r}")
        features = {key: finite(score[key], f"{cv}/{job}/{key}") for key in FEATURES}
        if features["bm25_score"] < 0 or not -1 <= features["cosine"] <= 1:
            raise ValueError(f"Score out of range at {cv}/{job}")
        rows.append(dict(cv_id=cv, job_id=job, **features, relevance=int(grade),
                         rank_bm25=int(score["rank_bm25"]), rank_embedding=int(score["rank_embedding"])))
    return rows


def fit_classifier(x, y):
    # Fit the scaler and classifier together, exclusively on the training rows.
    if len(set(y)) < 2:
        raise ValueError("Every training fold needs at least two classes")
    model = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, solver="lbfgs", max_iter=2000))
    model.fit(x, y)
    return model


def train(rows, out, k=5):
    pairs = {(r["cv_id"], r["job_id"]): r for r in rows}
    if len(pairs) != len(rows):
        raise ValueError("Duplicate training pair")
    cvs, jobs = complete_grid(pairs)
    validate_k(k, len(jobs))
    if len(cvs) < 2:
        raise ValueError("Leave-one-CV-out requires at least two CVs")
    out.mkdir(parents=True, exist_ok=False)
    x = np.array([[row[key] for key in FEATURES] for row in rows])
    y = np.array([row["relevance"] for row in rows])
    queries = np.array([row["cv_id"] for row in rows])
    predictions, evaluations = [], []
    for cv in sorted(set(queries)):
        test = queries == cv
        model = fit_classifier(x[~test], y[~test])
        expected_grades = model.predict_proba(x[test]) @ model.classes_
        held_out = [dict(rows[index], match_score=float(score))
                    for index, score in zip(np.flatnonzero(test), expected_grades)]
        held_out.sort(key=lambda r: (-r["match_score"], r["job_id"]))
        for rank, row in enumerate(held_out, 1):
            row["rank_classifier"] = rank
        predictions.extend(held_out)
        for method in ("bm25", "embedding", "classifier"):
            ordered = sorted(held_out, key=lambda r: r["rank_" + method])
            evaluations.append(dict(cv_id=cv, method=method, **metrics(ordered, k)))

    write_table(out / "training_pairs.csv", rows)
    write_table(out / "held_out_predictions.csv", predictions)
    write_table(out / "metrics_by_cv.csv", evaluations)
    print(f"Macro mean across held-out CVs (AI draft labels, Recall@{k})")
    summary = []
    for method in ("bm25", "embedding", "classifier"):
        items = [r for r in evaluations if r["method"] == method]
        entry = dict(method=method, **macro_metrics(items, k))
        summary.append(entry)
        print(entry)
    write_table(out / "macro_metrics.csv", summary)

    # Refit for later inference only after all held-out predictions are collected.
    final_model = fit_classifier(x, y)
    joblib.dump({"features": FEATURES, "pipeline": final_model,
                 "score": "expected relevance: sum(class_probability * class_grade)"},
                out / "match_classifier.joblib")
    print(f"Saved final classifier and evaluation tables to {out.resolve()}")
    return predictions, evaluations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores", type=Path, default=Path("results/embedding_vs_bm25.csv"))
    parser.add_argument("--labels", type=Path, required=True, help="Normalized label CSV from a baseline run")
    parser.add_argument("--output", type=Path, default=new_run_path(Path.cwd(), "supervised"))
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()
    try:
        scores = read_by_pair(args.scores, (*FEATURES, "rank_bm25", "rank_embedding"))
        labels = read_by_pair(args.labels, ("relevance_0_1_2",))
        train(training_rows(scores, labels), args.output, args.k)
    except (ValueError, OSError) as error:
        parser.exit(1, f"Training error: {error}\n")


if __name__ == "__main__":
    main()
