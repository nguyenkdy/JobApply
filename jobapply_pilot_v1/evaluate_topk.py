"""Compare ranked JD lists with the reviewed labels for the 6-CV pilot."""
import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean


def keyed_rows(path, fields):
    pairs = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = set(["cv_id", "job_id", *fields]) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing columns {sorted(missing)}")
        for row in reader:
            key = (row["cv_id"].strip(), row["job_id"].strip())
            if not all(key) or key in pairs:
                raise ValueError(f"{path}: empty or duplicate ID: {key}")
            pairs[key] = row
    return pairs


def dcg_at_k(grades, k):
    return sum((2 ** grade - 1) / math.log2(rank + 1)
               for rank, grade in enumerate(grades[:k], 1))


def evaluate(ranking_path, label_path, bm25_only=False, k=10):
    if not 1 <= k <= 50:
        raise ValueError("For this 50-JD pilot, k must be between 1 and 50.")
    methods = ["rank_bm25"] if bm25_only else ["rank_bm25", "rank_embedding"]
    rankings = keyed_rows(ranking_path, methods)
    labels = keyed_rows(label_path, ["relevance_0_1_2"])
    if labels.keys() != rankings.keys():
        raise ValueError("Label and ranking files must contain exactly the same CV-JD pairs.")
    jobs_by_cv = defaultdict(list)
    grades = {}
    for key, label in labels.items():
        value = label["relevance_0_1_2"].strip()
        if value not in {"0", "1", "2"}:
            raise ValueError(f"Missing or invalid label for {key}: {value!r}")
        grades[key] = int(value)
        jobs_by_cv[key[0]].append(key[1])
    if len(jobs_by_cv) != 6 or len({frozenset(ids) for ids in jobs_by_cv.values()}) != 1 or len(grades) != 300:
        raise ValueError("Expected six CVs, each paired with the same 50 JDs.")

    for method in methods:
        recalls, ndcgs = [], []
        print(f"\n{method}: CV | Top {k} labels | hits/strong | Recall@{k} | NDCG@{k}")
        for cv_id, jobs in sorted(jobs_by_cv.items()):
            by_rank = sorted((int(rankings[cv_id, job][method]), grades[cv_id, job]) for job in jobs)
            if [rank for rank, _ in by_rank] != list(range(1, len(jobs) + 1)):
                raise ValueError(f"{method}, {cv_id}: expected ranks 1 through 50.")
            ordered = [grade for _, grade in by_rank]
            total = ordered.count(2)
            hits = ordered[:k].count(2)
            ideal = dcg_at_k(sorted(ordered, reverse=True), k)
            recall = hits / total if total else None
            ndcg = dcg_at_k(ordered, k) / ideal if ideal else None
            if recall is not None:
                recalls.append(recall)
            if ndcg is not None:
                ndcgs.append(ndcg)
            print(f"{cv_id} | {ordered[:k]} | {hits}/{total} | {fmt(recall)} | {fmt(ndcg)}")
        print(f"Macro mean: Recall@{k}={fmt(mean(recalls) if recalls else None)} ({len(recalls)}/6 CVs), "
              f"NDCG@{k}={fmt(mean(ndcgs) if ndcgs else None)} ({len(ndcgs)}/6 CVs)")


def fmt(value):
    return "N/A" if value is None else f"{value:.4f}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path, default=Path("judgments_ai_draft.csv"))
    parser.add_argument("--rankings", type=Path, default=Path("results/embedding_vs_bm25.csv"))
    parser.add_argument("--bm25-only", action="store_true")
    parser.add_argument("--k", type=int, default=10, help="Ranking cutoff, 1 to 50 (default: 10)")
    args = parser.parse_args()
    try:
        evaluate(args.rankings, args.labels, args.bm25_only, args.k)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Evaluation error: {error}\n")
