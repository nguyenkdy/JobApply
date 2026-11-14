"""Reuse tested lexical/chunking behavior without executing pilot experiments."""
import importlib
from pathlib import Path
import sys
import time

import numpy as np

from ml_data.common import ROOT, file_hash, read_json, require


def pilot_module(name):
    path = str(ROOT / "jobapply_pilot_v1")
    if path not in sys.path:
        sys.path.insert(0, path)
    return importlib.import_module(name)


def lexical_index(jobs):
    return pilot_module("run_bm25").BM25([j["text_normalized"] for j in jobs])


def load_encoder(folder, lock_path):
    import torch
    from sentence_transformers import SentenceTransformer
    lock = read_json(lock_path)
    folder = Path(folder).resolve()
    require(lock["model"] == "intfloat/multilingual-e5-base", "Wrong E5 model")
    for name, expected in lock["files"].items():
        path = (folder / name).resolve()
        require(path.is_relative_to(folder) and file_hash(path) == expected["sha256"], "Encoder checksum mismatch: " + name)
    torch.manual_seed(20261113)
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    model = SentenceTransformer(str(folder), device="cpu", local_files_only=True, trust_remote_code=False)
    require(model.max_seq_length == lock["max_seq_length"] == 512, "Encoder token limit changed")
    return model


def encode(model, records, prefix):
    start = time.perf_counter()
    vectors, chunks = pilot_module("compare_embeddings").encode_texts(model, [r["text_normalized"] for r in records], prefix)
    require(np.isfinite(vectors).all(), "Invalid embeddings")
    return vectors, dict(seconds=time.perf_counter()-start, document_count=len(records), chunks=chunks,
                         dimension=int(vectors.shape[1]))
