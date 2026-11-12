"""Run from the extracted jobapply_pilot_v1 folder, beside run_bm25.py."""
import csv
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np

from run_bm25 import read_csv, run


ROOT = Path(__file__).resolve().parent
MODEL = "intfloat/multilingual-e5-small"


def split_for_model(text, fits):
    """Match the two-JD experiment's line boundaries. Also handle oversized lines."""
    if fits(text):
        return [text]
    chunks = []
    current = ""
    for line in text.splitlines():
        candidate = current + "\n" + line if current else line
        if fits(candidate):
            current = candidate
            continue
        if current.strip():
            chunks.append(current)
        current = line
        while not fits(current):
            # Split a long line without decoding and re-encoding token IDs.
            lo, hi = 0, len(current)
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if fits(current[:mid]):
                    lo = mid
                else:
                    hi = mid
            if lo == 0:
                raise ValueError("One character exceeds the token budget.")
            space = current.rfind(" ", 0, lo + 1)
            cut = space if space > 0 else lo
            part = current[:cut].strip()
            if part:
                chunks.append(part)
            current = current[cut:].lstrip()
    if current.strip():
        chunks.append(current)
    if not chunks or not all(fits(part) for part in chunks):
        raise ValueError("Invalid or oversized chunk.")
    return chunks


def encode_texts(model, texts, prefix):
    def fits(text):
        ids = model.tokenizer(prefix + text, truncation=False, verbose=False)["input_ids"]
        return len(ids) <= model.max_seq_length

    groups = [split_for_model(text, fits) for text in texts]
    flat = [part for group in groups for part in group]
    vectors = model.encode([prefix + part for part in flat], batch_size=4,
                           normalize_embeddings=True, convert_to_numpy=True,
                           show_progress_bar=True)
    pooled = []
    offset = 0
    for group in groups:
        block = vectors[offset:offset + len(group)]
        offset += len(group)
        if len(group) == 1:
            pooled.append(block[0])
        else:
            weights = [len(model.tokenizer(part, add_special_tokens=False,
                                           verbose=False)["input_ids"]) for part in group]
            center = np.average(block, axis=0, weights=weights)
            pooled.append(center / np.linalg.norm(center))
    return np.stack(pooled), [len(group) for group in groups]


def compare(cvs, jobs, baseline, cosines, cv_chunks, jd_chunks):
    lookup = {(r["cv_id"], r["job_id"]): r for r in baseline}
    rows = []
    for ci, cv in enumerate(cvs):
        order = sorted(range(len(jobs)), key=lambda j: (-cosines[ci, j], jobs[j]["job_id"]))
        for rank, ji in enumerate(order, 1):
            job = jobs[ji]
            bm = lookup[cv["cv_id"], job["job_id"]]
            rows.append({
                "cv_id": cv["cv_id"], "job_id": job["job_id"], "title": job["title_for_matching"],
                "rank_bm25": bm["rank_bm25"], "rank_embedding": rank,
                "rank_gain": bm["rank_bm25"] - rank,
                "bm25_score": bm["bm25_score"], "cosine": round(float(cosines[ci, ji]), 6),
                "cv_chunks": cv_chunks[ci], "jd_chunks": jd_chunks[ji],
            })
    return rows


def main():
    from sentence_transformers import SentenceTransformer

    jobs = read_csv(ROOT / "jobs_pilot.csv")
    cvs = read_csv(ROOT / "cvs_synthetic.csv")
    if len({r["job_id"] for r in jobs}) != 50 or len(jobs) != 50:
        raise ValueError("Expected the original pilot with 50 unique JDs.")
    if len({r["cv_id"] for r in cvs}) != 6 or len(cvs) != 6:
        raise ValueError("Expected 6 unique synthetic CVs.")
    baseline, _ = run(jobs, cvs)
    model = SentenceTransformer(MODEL, device="cpu")
    jd_vectors, jd_chunks = encode_texts(model, [r["match_text"] for r in jobs], "passage: ")
    cv_vectors, cv_chunks = encode_texts(model, [r["cv_text"] for r in cvs], "query: ")
    cosines = cv_vectors @ jd_vectors.T
    if not np.isfinite(cosines).all():
        raise ValueError("Non-finite cosine score.")
    rows = compare(cvs, jobs, baseline, cosines, cv_chunks, jd_chunks)
    path = ROOT / "results" / "embedding_vs_bm25.csv"
    path.parent.mkdir(exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8-sig", newline="", dir=path.parent,
                            delete=False) as temp:
        temp_path = Path(temp.name)
        writer = csv.DictWriter(temp, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    try:
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)

    print("\nPreviously tested pair (ranks are now within 50 JDs):")
    for row in rows:
        if row["cv_id"] == "CV_SYN_03" and row["job_id"] in {
                "job_3916eaf809684572fced", "job_27e84f3bd1762409744d"}:
            print(f"  {row['title']}: cosine={row['cosine']:.4f}, embedding rank={row['rank_embedding']}")
    for cv in cvs:
        ranked = [r for r in rows if r["cv_id"] == cv["cv_id"]]
        bm = min(ranked, key=lambda r: r["rank_bm25"])
        print(f"{cv['cv_id']} | BM25 #1: {bm['title']} | E5 #1: {ranked[0]['title']}")
    print(f"Saved {len(rows)} comparisons to {path}")


if __name__ == "__main__":
    main()
