"""Compare experience features on the fixed JobApply pilot. See HUONG_DAN.md."""
import argparse
import sys
from collections import defaultdict
from pathlib import Path

import joblib
import numpy as np
import sklearn

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from train_matcher import fit_classifier, read_by_pair, training_rows
from baseline_common import (catalog, complete_grid, finite, macro_metrics, metrics,
                             new_run_path, read_csv, sha256 as sha, validate_k,
                             validate_ranks, write_json, write_table)

EXPERIENCE_FEATURES = ("bm25_score", "cosine", "coverage", "gap_years_input")


def pair_features(score, requirements, experience):
    """Use already-rounded retrieval scores, as in the baseline training table."""
    return {**{key: finite(score[key], key) for key in ("bm25_score", "cosine") if key in score},
            **gap_features(requirements, experience)}


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


def experience_inputs(pilot, notes=None):
    notes = notes or HERE
    jobs = {r["job_id"]: r for r in catalog(pilot / "jobs_pilot.csv", "job_id", "match_text")}
    cvs = {r["cv_id"]: r for r in catalog(pilot / "cvs_synthetic.csv", "cv_id", "cv_text")}
    jd_notes = read_csv(notes / "jd_experience.csv", ("job_id", "scope", "threshold_months", "strictly_greater", "evidence"))
    cv_notes = read_csv(notes / "cv_experience.csv", ("cv_id", "scope", "months", "evidence"))
    if set(jobs) != {r["job_id"] for r in jd_notes} or set(cvs) != {r["cv_id"] for r in cv_notes}:
        raise ValueError("Annotations must cover exactly the input CVs and JDs.")
    for rows, id_key in ((jd_notes, "job_id"), (cv_notes, "cv_id")):
        keys = [(r[id_key], r["scope"]) for r in rows]
        if len(set(keys)) != len(keys):
            raise ValueError(f"Duplicate {id_key}/scope annotation")
    requirements = defaultdict(list)
    for row in jd_notes:
        if row["threshold_months"]:
            if not row["scope"] or int(row["threshold_months"]) < 0 or row["strictly_greater"] not in {"0", "1"}:
                raise ValueError("Invalid JD scope, months or strictness")
            if not row["evidence"].strip() or row["evidence"] not in jobs[row["job_id"]]["requirements_text"]:
                raise ValueError("JD evidence has changed: " + row["job_id"])
            requirements[row["job_id"]].append((row["scope"], int(row["threshold_months"]),
                                                row["strictly_greater"] == "1"))
    experience = defaultdict(dict)
    for row in cv_notes:
        if not row["scope"] or int(row["months"]) < 0:
            raise ValueError("Invalid CV scope or months")
        cv = cvs[row["cv_id"]]
        if cv["professional_summary"] != row["evidence"] or cv["experience_months"] != row["months"]:
            raise ValueError("CV evidence has changed: " + row["cv_id"])
        experience[row["cv_id"]][row["scope"]] = int(row["months"])
    return requirements, experience


def matrix(rows, features):
    return np.asarray([[r[key] for key in features] for r in rows], dtype=float)


def evaluated(rows, models, baseline_methods, k=5):
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
            evaluations.append(dict(cv_id=cv, method=name, **metrics(ordered, k)))
        predicted.extend(held_out)
    return predicted, evaluations


def main(args):
    pilot = args.pilot.resolve()
    label_path = args.labels or pilot / "judgments_ai_draft.csv"
    score_path = args.scores or pilot / "results" / ("rankings_all.csv" if args.lexical_check else "embedding_vs_bm25.csv")
    labels = read_by_pair(label_path, ["relevance_0_1_2"])
    notes = args.notes or HERE
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
                             bm25_score=finite(score["bm25_score"], f"{cv}/{job}"), rank_bm25=int(score["rank_bm25"])))
        validate_ranks(scores, "rank_bm25", "bm25_score")
        if any(r["bm25_score"] < 0 for r in rows):
            raise ValueError("Negative BM25 score")
        base = ["bm25_score"]
        methods = ["bm25"]
    else:
        scores = read_by_pair(score_path, ["bm25_score","cosine","rank_bm25","rank_embedding"])
        rows = training_rows(scores, labels)
        base = ["bm25_score","cosine"]
        methods = ["bm25","embedding"]
    cvs, job_ids = complete_grid(scores)
    validate_k(args.k, len(job_ids))
    if len(cvs) < 2:
        raise ValueError("Leave-one-CV-out requires at least two CVs")
    requirements, experience = experience_inputs(pilot, notes)
    jobs = read_csv(pilot / "jobs_pilot.csv")
    if set(scores) != {(c, j["job_id"]) for c in experience for j in jobs}:
        raise ValueError("Scores must cover the same input CVs and JDs.")
    for row in rows:
        row.update(pair_features(row, requirements[row["job_id"]], experience[row["cv_id"]]))

    # Separate the effect of knowing a comparable duration from the size of the shortfall.
    models = {"base_classifier": base, "coverage_control": base + ["coverage"],
              "experience_classifier": base + ["coverage","gap_years_input"]}
    out = args.output or new_run_path(pilot, "experience_v2")
    out.mkdir(parents=True, exist_ok=False)
    predicted, evaluations = evaluated(rows, models, methods, args.k)
    write_table(out / "experience_pairs.csv", rows)
    write_table(out / "held_out_predictions.csv", predicted)
    write_table(out / "metrics_by_cv.csv", evaluations)
    summary = []
    for name in [*methods, *models]:
        entries = [r for r in evaluations if r["method"] == name]
        summary.append(dict(method=name, **macro_metrics(entries, args.k)))
    write_table(out / "macro_metrics.csv", summary)
    print(f"Leave-one-CV-out results ({len(cvs)} CVs, same {len(job_ids)} jobs; AI draft labels)")
    for row in summary:
        print(row)
    # Refit for inference after cross-validation; independent of metric calculation.
    features = models["experience_classifier"]
    final_model = fit_classifier(matrix(rows, features), [r["relevance"] for r in rows])
    joblib.dump(dict(features=features, pipeline=final_model, version=2,
                     score="expected relevance on 0..2", mode="lexical" if args.lexical_check else "full"),
                out / "experience_classifier.joblib")
    report = dict(score_file_sha256=sha(score_path), label_file_sha256=sha(label_path),
                  job_notes_sha256=sha(notes/"jd_experience.csv"), cv_notes_sha256=sha(notes/"cv_experience.csv"),
                  sklearn_version=sklearn.__version__, features=features, pair_count=len(rows),
                  pairs_with_measured_gap=sum(r["gap_months_observed"] is not None for r in rows),
                  pairs_with_positive_gap=sum(r["gap_years_input"]>0 for r in rows),
                  scope="Development pilot; AI-proposed labels; held-out CVs, shared JDs.")
    write_json(out / "run_info.json", dict(report, k=args.k))
    print("Saved results:", out.resolve())
    return predicted, evaluations


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, default=Path.cwd())
    parser.add_argument("--scores", type=Path)
    parser.add_argument("--labels", type=Path, required=True, help="Normalized label CSV from a baseline run")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--notes", type=Path)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--lexical-check", action="store_true")
    try:
        main(parser.parse_args())
    except (OSError, ValueError, KeyError) as exc:
        sys.exit(f"Experiment error: {exc}")
