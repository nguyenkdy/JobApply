"""Compare experience features on the fixed JobApply pilot. See HUONG_DAN.md."""
import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

import joblib
import numpy as np
import sklearn

from train_matcher import fit_classifier, metrics, read_by_pair, training_rows, write_table

HERE = Path(__file__).resolve().parent


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gap_features(requirements, experience):
    known_gaps = []
    for scope, threshold, strict in requirements:
        if scope in experience:
            # Month is the resolution of the pilot CVs: >36 means at least 37.
            known_gaps.append(max(0, threshold + int(strict) - experience[scope]))
    measured = max(known_gaps) if known_gaps else None
    return {
        "known_constraints": len(known_gaps),
        "numeric_constraints": len(requirements),
        "gap_months_observed": measured,
        "coverage": len(known_gaps) / len(requirements) if requirements else 0.0,
        "gap_years_input": measured / 12 if measured is not None else 0.0,
    }


def experience_inputs(pilot):
    jobs = {r["job_id"]: r for r in read_csv(pilot / "jobs_pilot.csv")}
    cvs = {r["cv_id"]: r for r in read_csv(pilot / "cvs_synthetic.csv")}
    jd_notes = read_csv(HERE / "jd_experience.csv")
    cv_notes = read_csv(HERE / "cv_experience.csv")
    if set(jobs) != {r["job_id"] for r in jd_notes} or set(cvs) != {r["cv_id"] for r in cv_notes}:
        raise ValueError("Use the original 50 JDs and 6 CVs for these source annotations.")
    requirements = defaultdict(list)
    for row in jd_notes:
        if row["threshold_months"]:
            if row["evidence"] not in jobs[row["job_id"]]["requirements_text"]:
                raise ValueError("JD evidence has changed: " + row["job_id"])
            requirements[row["job_id"]].append((row["scope"], int(row["threshold_months"]),
                                                row["strictly_greater"] == "1"))
    experience = defaultdict(dict)
    for row in cv_notes:
        cv = cvs[row["cv_id"]]
        if cv["professional_summary"] != row["evidence"] or cv["experience_months"] != row["months"]:
            raise ValueError("CV evidence has changed: " + row["cv_id"])
        experience[row["cv_id"]][row["scope"]] = int(row["months"])
    return requirements, experience


def matrix(rows, features):
    return np.asarray([[r[key] for key in features] for r in rows], dtype=float)


def evaluated(rows, models, baseline_methods):
    predicted, evaluations = [], []
    for cv in sorted({r["cv_id"] for r in rows}):
        training = [r for r in rows if r["cv_id"] != cv]
        held_out = [r.copy() for r in rows if r["cv_id"] == cv]
        y = [r["relevance"] for r in training]
        for name, features in models.items():
            model = fit_classifier(matrix(training, features), y)
            scores = model.predict_proba(matrix(held_out, features)) @ model.classes_
            for row, score in zip(held_out, scores):
                row["score_" + name] = float(score)
            ranked = sorted(held_out, key=lambda r: (-r["score_" + name], r["job_id"]))
            for rank, row in enumerate(ranked, 1):
                row["rank_" + name] = rank
        for name in [*baseline_methods, *models]:
            ordered = sorted(held_out, key=lambda r: r["rank_" + name])
            evaluations.append(dict(cv_id=cv, method=name, **metrics(ordered)))
        predicted.extend(held_out)
    return predicted, evaluations


def average_metric(entries, key):
    values = [r[key] for r in entries if r[key] is not None]
    return mean(values) if values else None


def main(args):
    pilot = args.pilot.resolve()
    label_path = args.labels or pilot / "judgments_ai_draft.csv"
    score_path = args.scores or pilot / "results" / ("rankings_all.csv" if args.lexical_check else "embedding_vs_bm25.csv")
    labels = read_by_pair(label_path, ["relevance_0_1_2"])
    if args.lexical_check:
        # Real BM25-only control; never use it as a stand-in for E5.
        scores = read_by_pair(score_path, ["rank_bm25", "bm25_score"])
        rows = []
        if labels.keys() != scores.keys():
            raise ValueError("Mismatched label and ranking pairs.")
        for (cv, job), score in sorted(scores.items()):
            grade = labels[cv,job]["relevance_0_1_2"].strip()
            if grade not in {"0","1","2"}:
                raise ValueError("Invalid relevance grade.")
            rows.append(dict(cv_id=cv, job_id=job, relevance=int(grade),
                             bm25_score=float(score["bm25_score"]), rank_bm25=int(score["rank_bm25"])))
        base = ["bm25_score"]
        methods = ["bm25"]
    else:
        scores = read_by_pair(score_path, ["bm25_score","cosine","rank_bm25","rank_embedding"])
        rows = training_rows(scores, labels)
        base = ["bm25_score","cosine"]
        methods = ["bm25","embedding"]
    requirements, experience = experience_inputs(pilot)
    jobs = read_csv(pilot / "jobs_pilot.csv")
    if set(scores) != {(c, j["job_id"]) for c in experience for j in jobs}:
        raise ValueError("Scores must cover the same input CVs and JDs.")
    for row in rows:
        row.update(gap_features(requirements[row["job_id"]], experience[row["cv_id"]]))

    # Separate the effect of knowing a comparable duration from the size of the shortfall.
    models = {"base_classifier": base, "coverage_control": base + ["coverage"],
              "experience_classifier": base + ["coverage","gap_years_input"]}
    predicted, evaluations = evaluated(rows, models, methods)
    out = args.output or pilot / "results" / ("experience_lexical_control" if args.lexical_check else "experience_v2")
    out.mkdir(parents=True, exist_ok=True)
    write_table(out / "experience_pairs.csv", rows)
    write_table(out / "held_out_predictions.csv", predicted)
    write_table(out / "metrics_by_cv.csv", evaluations)
    summary = []
    for name in [*methods, *models]:
        entries = [r for r in evaluations if r["method"] == name]
        summary.append(dict(method=name, recall_at_5=average_metric(entries,"recall_at_5"),
                            ndcg_at_5=average_metric(entries,"ndcg_at_5")))
    write_table(out / "macro_metrics.csv", summary)
    print("Leave-one-CV-out results (6 CVs, same 50 jobs)")
    for row in summary:
        print(f"{row['method']:24s} Recall@5={row['recall_at_5']:.4f}   NDCG@5={row['ndcg_at_5']:.4f}")
    # Refit for inference after cross-validation; independent of metric calculation.
    features = models["experience_classifier"]
    final_model = fit_classifier(matrix(rows, features), [r["relevance"] for r in rows])
    joblib.dump(dict(features=features, pipeline=final_model, version=2,
                     score="expected relevance on 0..2", mode="lexical" if args.lexical_check else "full"),
                out / "experience_classifier.joblib")
    report = dict(score_file_sha256=sha(score_path), label_file_sha256=sha(label_path),
                  job_notes_sha256=sha(HERE/"jd_experience.csv"), cv_notes_sha256=sha(HERE/"cv_experience.csv"),
                  sklearn_version=sklearn.__version__, features=features, pair_count=len(rows),
                  pairs_with_measured_gap=sum(r["gap_months_observed"] is not None for r in rows),
                  pairs_with_positive_gap=sum(r["gap_years_input"]>0 for r in rows),
                  scope="Development pilot; AI-proposed labels; held-out CVs, shared JDs.")
    (out/"run_info.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    best = max(summary, key=lambda r: (r["ndcg_at_5"], r["recall_at_5"]))
    print("Highest pilot NDCG@5:", best["method"])
    print("Saved results:", out.resolve())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, default=Path.cwd())
    parser.add_argument("--scores", type=Path)
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--lexical-check", action="store_true")
    try:
        main(parser.parse_args())
    except (OSError, ValueError, KeyError) as exc:
        sys.exit(f"Experiment error: {exc}")
