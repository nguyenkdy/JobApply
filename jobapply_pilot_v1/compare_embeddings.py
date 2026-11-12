"""Run from the extracted jobapply_pilot_v1 folder, beside run_bm25.py."""
import argparse
import json
from pathlib import Path

import numpy as np

from run_bm25 import run
from baseline_common import catalog, new_run_path, sha256, write_json, write_table


ROOT = Path(__file__).resolve().parent
MODEL = "intfloat/multilingual-e5-small"
REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"


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


def encoder_snapshot(local_files_only=True):
    from huggingface_hub import snapshot_download
    lock = json.loads((ROOT / "encoder.lock.json").read_text(encoding="utf-8"))
    if (lock["model"], lock["revision"]) != (MODEL, REVISION):
        raise ValueError("Encoder code and lock disagree")
    snapshot = Path(snapshot_download(MODEL, revision=REVISION, local_files_only=local_files_only,
                                     allow_patterns=list(lock["files"])))
    for name, expected in lock["files"].items():
        if sha256(snapshot / name) != expected["sha256"]:
            raise ValueError(f"Encoder file checksum mismatch: {name}")
    return snapshot, lock


def generate(jobs, cvs, baseline, local_files_only=True):
    import torch
    from sentence_transformers import SentenceTransformer

    torch.manual_seed(0)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    snapshot, lock = encoder_snapshot(local_files_only)
    model = SentenceTransformer(str(snapshot), device="cpu", local_files_only=True, trust_remote_code=False)
    if model.max_seq_length != lock["max_seq_length"]:
        raise ValueError("Encoder token limit differs from lock")
    jd_vectors, jd_chunks = encode_texts(model, [r["match_text"] for r in jobs], "passage: ")
    cv_vectors, cv_chunks = encode_texts(model, [r["cv_text"] for r in cvs], "query: ")
    cosines = cv_vectors @ jd_vectors.T
    if not np.isfinite(cosines).all():
        raise ValueError("Non-finite cosine score.")
    return compare(cvs, jobs, baseline, cosines, cv_chunks, jd_chunks), dict(
        model=MODEL, revision=REVISION, device="cpu", max_seq_length=model.max_seq_length,
        query_prefix="query: ", passage_prefix="passage: ", batch_size=4,
        pooling="normalized chunks; token-weighted mean; L2 normalization",
        torch_threads=1, seed=0, deterministic_algorithms=True,
        score_decimals=6, local_files_only=local_files_only)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=new_run_path(ROOT, "embedding"))
    parser.add_argument("--allow-download", action="store_true")
    args = parser.parse_args()
    jobs = catalog(args.pilot / "jobs_pilot.csv", "job_id", "match_text")
    cvs = catalog(args.pilot / "cvs_synthetic.csv", "cv_id", "cv_text")
    args.output.mkdir(parents=True, exist_ok=False)
    baseline, _ = run(jobs, cvs)
    rows, info = generate(jobs, cvs, baseline, not args.allow_download)
    write_table(args.output / "embedding_vs_bm25.csv", rows)
    write_json(args.output / "encoder.json", info)
    print(json.dumps(info))
    print(f"Saved {len(rows)} comparisons to {args.output}")


if __name__ == "__main__":
    main()
