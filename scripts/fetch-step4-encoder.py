"""Download only the pinned public encoder. No CV/JD files are transmitted."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml_data.common import file_hash, read_json, require

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=Path("docs/ml/data_configs/step4_encoder.lock.json"))
    parser.add_argument("--output", type=Path, default=Path(".tools/ml-models/multilingual-e5-base-d1287505"))
    args = parser.parse_args()
    from huggingface_hub import snapshot_download
    lock = read_json(args.lock)
    snapshot_download(lock["model"], revision=lock["revision"], local_dir=args.output,
                      allow_patterns=list(lock["files"]), max_workers=3)
    require(all(file_hash(args.output / name) == info["sha256"] for name, info in lock["files"].items()), "Encoder hash mismatch")
    print("Pinned encoder verified:", args.output)
