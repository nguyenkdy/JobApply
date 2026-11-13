"""PowerShell: python -m ml_data {inventory,ingest,split,audit,sample,verify}."""
import argparse
import json
from pathlib import Path

from .common import ROOT, verify
from .ingest import ingest, inventory
from .sampling import sample_pairs
from .splitting import audit_split, make_split


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inv = sub.add_parser("inventory")
    inv.add_argument("--workspace", type=Path, default=ROOT)
    inv.add_argument("--output", type=Path, required=True)
    imp = sub.add_parser("ingest")
    imp.add_argument("--config", type=Path, required=True)
    imp.add_argument("--output", type=Path, required=True)
    split = sub.add_parser("split")
    split.add_argument("--dataset", type=Path, required=True)
    split.add_argument("--output", type=Path, required=True)
    split.add_argument("--mode", choices=("known-jd", "new-both"), required=True)
    split.add_argument("--seed", type=int, default=20261113)
    split.add_argument("--ratios", type=float, nargs=3, default=(0.6, 0.2, 0.2))
    audit = sub.add_parser("audit")
    audit.add_argument("--dataset", type=Path, required=True)
    audit.add_argument("--split", type=Path, required=True)
    sample = sub.add_parser("sample")
    sample.add_argument("--dataset", type=Path, required=True)
    sample.add_argument("--split", type=Path, required=True)
    sample.add_argument("--output", type=Path, required=True)
    sample.add_argument("--partition", choices=("train", "validation", "test"), default="train")
    sample.add_argument("--strategy", choices=("mixed", "census"), default="mixed")
    sample.add_argument("--seed", type=int, default=20261113)
    sample.add_argument("--random-per-cv", type=int, default=3)
    sample.add_argument("--hard-per-type", type=int, default=2)
    sample.add_argument("--max-pairs", type=int, default=100000)
    check = sub.add_parser("verify")
    check.add_argument("--artifact", type=Path, required=True)
    upstream = sub.add_parser("upstream", help="Audit three supplied stages; import JD and select a development batch")
    upstream.add_argument("--source-dir", type=Path, default=ROOT)
    upstream.add_argument("--output", type=Path, required=True)
    upstream.add_argument("--seed", type=int, default=20261113)
    synthetic = sub.add_parser("synthetic-cvs", help="Render versioned authored synthetic scenarios with evidence")
    synthetic.add_argument("--assets", type=Path, default=ROOT / "ml_data_assets/synthetic_cv_v1")
    synthetic.add_argument("--output", type=Path, required=True)
    expansion = sub.add_parser("expand-preview", help="Frozen v2 JD + synthetic CV import and known-JD preview")
    expansion.add_argument("--upstream-run", type=Path, required=True)
    expansion.add_argument("--cv-batch", type=Path, required=True)
    expansion.add_argument("--output", type=Path, required=True)
    expansion.add_argument("--seed", type=int, default=20261113)
    args = parser.parse_args()
    try:
        if args.command == "inventory":
            result = inventory(args.workspace, args.output)
        elif args.command == "ingest":
            result = ingest(args.config, args.output)
        elif args.command == "split":
            result = make_split(args.dataset, args.output, args.mode, args.seed, args.ratios)
        elif args.command == "audit":
            result = audit_split(args.dataset, args.split)
        elif args.command == "sample":
            result = sample_pairs(args.dataset, args.split, args.output, args.partition, args.strategy, args.seed,
                                  args.random_per_cv, args.hard_per_type, args.max_pairs)
        elif args.command == "synthetic-cvs":
            from .synthetic import render_batch
            result = render_batch(args.assets, args.output)
        elif args.command == "expand-preview":
            from .expansion import prepare_expansion
            result = prepare_expansion(args.upstream_run, args.cv_batch, args.output, args.seed)
        elif args.command == "upstream":
            from .upstream import prepare_upstream
            full = prepare_upstream(args.source_dir, args.output, args.seed)
            result = {k: full[k] for k in ("source_hashes", "relations", "import_summary", "batch")}
        else:
            manifest = verify(args.artifact)
            result = dict(verified=True, artifact_type=manifest["artifact_type"], files=len(manifest["artifacts"]))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Data preparation error: {exc}\n")


if __name__ == "__main__":
    main()
