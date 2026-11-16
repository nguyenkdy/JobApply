"""PowerShell: python -m ml_experiment --help"""
import argparse
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preparation", type=Path, required=True)
    parser.add_argument("--encoder", type=Path, required=True)
    parser.add_argument("--encoder-lock", type=Path, default=Path("docs/ml/data_configs/step4_encoder.lock.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    from .runner import run
    try:
        result = run(args.preparation, args.encoder, args.encoder_lock, args.output)
        print(json.dumps({k: result[k] for k in ("selected", "validation", "test")}, indent=2))
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"Experiment failed (original inputs preserved): {exc}\n")


if __name__ == "__main__":
    main()
