"""Evaluate a complete development CV-JD grid; labels are not human gold."""
import argparse
from pathlib import Path
from baseline_common import (complete_grid, keyed_rows, macro_metrics, metrics,
                             validate_k, validate_ranks)


def evaluate(ranking_path, label_path, bm25_only=False, k=5):
    methods = ["bm25"] if bm25_only else ["bm25", "embedding"]
    rankings = keyed_rows(ranking_path, ["rank_" + m for m in methods])
    labels = keyed_rows(label_path, ["relevance_0_1_2"])
    if labels.keys() != rankings.keys():
        raise ValueError("Label and ranking files must contain exactly the same pairs")
    cvs, jobs = complete_grid(rankings)
    validate_k(k, len(jobs))
    for key, row in labels.items():
        if row["relevance_0_1_2"] not in {"0", "1", "2"}:
            raise ValueError(f"Invalid label at {key}")
    evaluations = []
    for method in methods:
        validate_ranks(rankings, "rank_" + method)
        for cv in cvs:
            ordered = sorted((dict(rankings[cv, j], relevance=int(labels[cv, j]["relevance_0_1_2"]))
                              for j in jobs), key=lambda r: int(r["rank_" + method]))
            entry = dict(cv_id=cv, method=method, **metrics(ordered, k))
            evaluations.append(entry)
            print(entry)
        print(dict(method=method, **macro_metrics([r for r in evaluations if r["method"] == method], k)))
    return evaluations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path, required=True, help="Normalized label CSV from a baseline run")
    parser.add_argument("--rankings", type=Path, default=Path("results/embedding_vs_bm25.csv"))
    parser.add_argument("--bm25-only", action="store_true")
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()
    try:
        evaluate(args.rankings, args.labels, args.bm25_only, args.k)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Evaluation error: {error}\n")


if __name__ == "__main__":
    main()
