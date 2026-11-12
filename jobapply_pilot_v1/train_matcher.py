"""Train and evaluate a two-feature CV-JD classifier on the JobApply pilot."""
import argparse
import csv
import math
from pathlib import Path
from statistics import mean

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


FEATURES = ("bm25_score", "cosine")


def read_by_pair(path, columns):
    data = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"cv_id", "job_id", *columns}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"{path}: missing columns {required - set(reader.fieldnames or [])}")
        for row in reader:
            key = (row["cv_id"].strip(), row["job_id"].strip())
            if not all(key) or key in data:
                raise ValueError(f"{path}: empty or duplicate key {key}")
            data[key] = row
    return data


def write_table(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def training_rows(scores, judgments):
    if scores.keys() != judgments.keys():
        raise ValueError("The score and label files must contain exactly the same CV-JD pairs.")
    cvs = sorted({cv for cv, _ in scores})
    jobs = {job for _, job in scores}
    if (len(cvs), len(jobs), len(scores)) != (6, 50, 300):
        raise ValueError("This pilot expects six CVs and all 50 jobs per CV.")
    rows = []
    for (cv, job), score in sorted(scores.items()):
        grade = judgments[cv, job]["relevance_0_1_2"].strip()
        if grade not in {"0", "1", "2"}:
            raise ValueError(f"Invalid grade at {cv}/{job}: {grade!r}")
        features = {key: float(score[key]) for key in FEATURES}
        if not all(math.isfinite(value) for value in features.values()):
            raise ValueError(f"Non-finite score at {cv}/{job}")
        rows.append(dict(cv_id=cv, job_id=job, **features, relevance=int(grade),
                         rank_bm25=int(score["rank_bm25"]), rank_embedding=int(score["rank_embedding"])))
    for cv in cvs:
        for column in ("rank_bm25", "rank_embedding"):
            if sorted(r[column] for r in rows if r["cv_id"] == cv) != list(range(1, 51)):
                raise ValueError(f"{cv}: invalid ranks in {column}")
    return rows


def fit_classifier(x, y):
    # Fit the scaler and classifier together, exclusively on the training rows.
    model = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, solver="lbfgs", max_iter=2000))
    model.fit(x, y)
    return model


def dcg5(labels):
    return sum((2**grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(labels[:5], 1))


def metrics(ordered):
    grades = [row["relevance"] for row in ordered]
    strong = grades.count(2)
    ideal = dcg5(sorted(grades, reverse=True))
    return dict(recall_at_5=grades[:5].count(2) / strong if strong else None,
                ndcg_at_5=dcg5(grades) / ideal if ideal else None)


def train(rows, out):
    out.mkdir(parents=True, exist_ok=True)
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
            evaluations.append(dict(cv_id=cv, method=method, **metrics(ordered)))

    write_table(out / "training_pairs.csv", rows)
    write_table(out / "held_out_predictions.csv", predictions)
    write_table(out / "metrics_by_cv.csv", evaluations)
    print("Macro mean across held-out CVs (label 2 = relevant for Recall@5)")
    for method in ("bm25", "embedding", "classifier"):
        items = [r for r in evaluations if r["method"] == method]
        parts = []
        for key in ("recall_at_5", "ndcg_at_5"):
            defined = [r[key] for r in items if r[key] is not None]
            value = f"{mean(defined):.4f}" if defined else "N/A"
            parts.append(f"{key}={value} ({len(defined)} CVs)")
        print(f"{method:12} " + " | ".join(parts))

    # Refit for later inference only after all held-out predictions are collected.
    final_model = fit_classifier(x, y)
    joblib.dump({"features": FEATURES, "pipeline": final_model,
                 "score": "expected relevance: sum(class_probability * class_grade)"},
                out / "match_classifier.joblib")
    print(f"Saved final classifier and evaluation tables to {out.resolve()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores", type=Path, default=Path("results/embedding_vs_bm25.csv"))
    parser.add_argument("--labels", type=Path, default=Path("judgments_ai_draft.csv"))
    parser.add_argument("--output", type=Path, default=Path("results/supervised"))
    args = parser.parse_args()
    try:
        scores = read_by_pair(args.scores, (*FEATURES, "rank_bm25", "rank_embedding"))
        labels = read_by_pair(args.labels, ("relevance_0_1_2",))
        train(training_rows(scores, labels), args.output)
    except (ValueError, OSError) as error:
        parser.exit(1, f"Training error: {error}\n")
