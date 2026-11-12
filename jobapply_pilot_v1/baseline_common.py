"""Shared validation, metrics and artifact I/O for the development pilot."""
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_csv(path, required=(), allow_legacy_blank=False):
    path = Path(path)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        if not fields or len(set(fields)) != len(fields):
            raise ValueError(f"{path}: empty/duplicate header")
        if any(not f.strip() for f in fields) and not allow_legacy_blank:
            raise ValueError(f"{path}: unnamed column; normalize the legacy label file first")
        if not set(required).issubset(fields):
            raise ValueError(f"{path}: missing columns {set(required) - set(fields)}")
        rows = list(reader)
        if not rows:
            raise ValueError(f"{path}: empty table")
        for number, row in enumerate(rows, 2):
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f"{path}:{number}: wrong number of cells")
    return rows


def keyed_rows(path, columns=()):
    data = {}
    for row in read_csv(path, ("cv_id", "job_id", *columns)):
        key = row["cv_id"], row["job_id"]
        if any(not v or v != v.strip() for v in key) or key in data:
            raise ValueError(f"{path}: empty, padded or duplicate key {key}")
        data[key] = row
    return data


def catalog(path, id_column, text_column):
    rows = read_csv(path, (id_column, text_column))
    ids = [r[id_column] for r in rows]
    if len(set(ids)) != len(ids) or any(not v or v != v.strip() for v in ids):
        raise ValueError(f"{path}: empty, padded or duplicate {id_column}")
    if any(not r[text_column].strip() for r in rows):
        raise ValueError(f"{path}: empty {text_column}")
    return rows


def complete_grid(pairs, cv_ids=None, job_ids=None):
    if not pairs:
        raise ValueError("Empty CV-JD grid")
    cvs = set(cv_ids) if cv_ids is not None else {c for c, _ in pairs}
    jobs = set(job_ids) if job_ids is not None else {j for _, j in pairs}
    if set(pairs) != {(c, j) for c in cvs for j in jobs}:
        raise ValueError("Expected the complete CV x JD grid with no unknown IDs")
    return sorted(cvs), sorted(jobs)


def finite(value, context):
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context}: invalid number {value!r}") from exc
    if not math.isfinite(result):
        raise ValueError(f"{context}: non-finite number")
    return result


def validate_ranks(pairs, rank_column, score_column=None):
    cvs, jobs = complete_grid(pairs)
    for cv in cvs:
        rows = [pairs[cv, job] for job in jobs]
        ranks = [int(r[rank_column]) for r in rows]
        if sorted(ranks) != list(range(1, len(jobs) + 1)):
            raise ValueError(f"{cv}: invalid ranks in {rank_column}")
        if score_column:
            ordered = sorted(rows, key=lambda r: int(r[rank_column]))
            scores = [finite(r[score_column], f"{cv}/{r['job_id']}/{score_column}") for r in ordered]
            if scores != sorted(scores, reverse=True):
                raise ValueError(f"{cv}: ranks contradict {score_column}")
            # Stored rounded scores can tie although the original unrounded scores differ.


def validate_k(k, job_count):
    if type(k) is not int or not 1 <= k <= job_count:
        raise ValueError(f"k must be between 1 and {job_count}")


def dcg_at_k(grades, k):
    return sum((2 ** grade - 1) / math.log2(rank + 1)
               for rank, grade in enumerate(grades[:k], 1))


def metrics(ordered, k=5):
    validate_k(k, len(ordered))
    grades = [r["relevance"] for r in ordered]
    if any(type(v) is not int or v not in (0, 1, 2) for v in grades):
        raise ValueError("Invalid relevance grade")
    strong = grades.count(2)
    ideal = dcg_at_k(sorted(grades, reverse=True), k)
    return {f"recall_at_{k}": grades[:k].count(2) / strong if strong else None,
            f"ndcg_at_{k}": dcg_at_k(grades, k) / ideal if ideal else None}


def macro_metrics(entries, k=5):
    result = {}
    for key in (f"recall_at_{k}", f"ndcg_at_{k}"):
        values = [r[key] for r in entries if r[key] is not None]
        result[key] = mean(values) if values else None
        result[key + "_defined_cvs"] = len(values)
        result[key + "_excluded_cvs"] = len(entries) - len(values)
    return result


def write_table(path, rows, fields=None):
    # New artifacts: UTF-8 without BOM, LF records AND embedded newlines.
    with Path(path).open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def new_run_path(root, name):
    return Path(root) / "results" / "reruns" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ") + "_" + name)
