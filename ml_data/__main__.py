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
    split.add_argument("--eval-jd-per-role", type=int, default=None)
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
    extract_jd = sub.add_parser("extract-jd", help="Evidence-backed rule extraction of JD role, skills, stack and experience")
    extract_jd.add_argument("--upstream-run", type=Path, required=True)
    extract_jd.add_argument("--output", type=Path, required=True)
    val_labels = sub.add_parser("validate-labels", help="Validate annotated pair CSV against base pair CSV and rubric rules")
    val_labels.add_argument("--pairs", type=Path, required=True)
    val_labels.add_argument("--labels", type=Path, required=True)
    lab_pairs = sub.add_parser("label-pairs", help="Label CV-JD pairs directly from established evidence criteria")
    lab_pairs.add_argument("--dataset", type=Path, required=True)
    lab_pairs.add_argument("--pairs", type=Path, required=True)
    lab_pairs.add_argument("--jd-extraction", type=Path, default=None)
    lab_pairs.add_argument("--output", type=Path, required=True)
    experiment = sub.add_parser("prepare-experiment", help="Complete data prerequisites and stop before scoring/training")
    experiment.add_argument("--upstream-run", type=Path, required=True)
    experiment.add_argument("--audited-run", type=Path, required=True)
    experiment.add_argument("--reference-run", type=Path, required=True)
    experiment.add_argument("--prior-cv-batch", type=Path, required=True)
    experiment.add_argument("--assets", type=Path, default=ROOT / "ml_data_assets/independent_cv_v3")
    experiment.add_argument("--output", type=Path, required=True)
    precheck = sub.add_parser("check-pretraining", help="Recompute all input/lineage/grid/label gates without training")
    precheck.add_argument("--artifact", type=Path, required=True)
    full_jd = sub.add_parser("expand-jd-catalogue", help="Import all eligible JD; preserve unknowns, groups and completed-benchmark exposure")
    full_jd.add_argument("--preparation", type=Path, required=True)
    full_jd.add_argument("--benchmark", type=Path, required=True)
    full_jd.add_argument("--output", type=Path, required=True)
    refine = sub.add_parser("refine-jd-catalogue", help="Versioned metadata overlay and CV design; no labels or training")
    refine.add_argument("--catalogue-run", type=Path, required=True)
    refine.add_argument("--output", type=Path, required=True)
    intake = sub.add_parser("prepare-cv-intake", help="Admit individual full-text CV sources; preview on all known JD")
    intake.add_argument("--metadata-run", type=Path, required=True)
    intake.add_argument("--catalogue-run", type=Path, required=True)
    intake.add_argument("--preparation-run", type=Path, required=True)
    intake.add_argument("--assets", type=Path, default=ROOT / "ml_data_assets/authored_cv_v6")
    intake.add_argument("--output", type=Path, required=True)
    intake.add_argument("--prior-intake", type=Path, default=None)
    intake_check = sub.add_parser("check-cv-intake")
    intake_check.add_argument("--artifact", type=Path, required=True)
    proxy = sub.add_parser("prepare-expanded-labels", help="Frozen bounded proxy policy; sampled train and full evaluation census; no training")
    proxy.add_argument("--intake", type=Path, required=True)
    proxy.add_argument("--output", type=Path, required=True)
    proxy_check = sub.add_parser("check-expanded-labels")
    proxy_check.add_argument("--intake", type=Path, required=True)
    proxy_check.add_argument("--artifact", type=Path, required=True)
    readiness = sub.add_parser("audit-readiness", help="Explain protected-input drift and frozen missing-label decisions; no new labels")
    readiness.add_argument("--intake", type=Path, required=True)
    readiness.add_argument("--labels", type=Path, required=True)
    readiness.add_argument("--receipt", type=Path, default=ROOT / "docs/ml/reports/20261116-retired-200-cv-cleanup.json")
    readiness.add_argument("--output", type=Path, required=True)
    revision = sub.add_parser("prepare-label-revision", help="v2 evidence policy on development cohort; preserve original partitions, no training")
    revision.add_argument("--intake", type=Path, required=True)
    revision.add_argument("--old-labels", type=Path, required=True)
    revision.add_argument("--audit", type=Path, required=True)
    revision.add_argument("--output", type=Path, required=True)
    revision_check = sub.add_parser("check-label-revision")
    revision_check.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "inventory":
            result = inventory(args.workspace, args.output)
        elif args.command == "ingest":
            result = ingest(args.config, args.output)
        elif args.command == "split":
            result = make_split(args.dataset, args.output, args.mode, args.seed, args.ratios, args.eval_jd_per_role)
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
        elif args.command == "extract-jd":
            from .extraction import enrich_upstream_jds
            result = enrich_upstream_jds(args.upstream_run, args.output)
        elif args.command == "validate-labels":
            from .annotation import validate_labels
            result = validate_labels(args.pairs, args.labels)
        elif args.command == "label-pairs":
            from .annotation import label_pairs_by_evidence
            result = label_pairs_by_evidence(args.dataset, args.pairs, args.jd_extraction, args.output)
        elif args.command == "prepare-experiment":
            from .pretraining import prepare_experiment
            result = prepare_experiment(args.upstream_run, args.audited_run, args.reference_run,
                                       args.prior_cv_batch, args.assets, args.output)
        elif args.command == "check-pretraining":
            from .pretraining import check_conditions
            result = check_conditions(args.artifact)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            parser.exit(0 if result["ready_for_automatic_label_experiment"] else 1)
        elif args.command == "expand-jd-catalogue":
            from .catalogue import expand_catalogue
            full = expand_catalogue(args.preparation, args.benchmark, args.output)
            result = {k: full[k] for k in ("source_jd_count", "catalogue_count", "catalogue_groups", "dispositions", "metadata_missing", "labels_created", "final_test_ready")}
        elif args.command == "refine-jd-catalogue":
            from .refinement import refine_catalogue
            result = refine_catalogue(args.catalogue_run, args.output)
        elif args.command == "prepare-cv-intake":
            from .intake import prepare_intake
            result = prepare_intake(args.metadata_run, args.catalogue_run, args.preparation_run, args.assets, args.output, args.prior_intake)
        elif args.command == "check-cv-intake":
            from .intake import check_intake
            result = check_intake(args.artifact)
        elif args.command == "prepare-expanded-labels":
            from .expanded_labels import create_labels
            result = create_labels(args.intake, args.output)
        elif args.command == "check-expanded-labels":
            from .expanded_labels import check_labels
            result = check_labels(args.intake, args.artifact)
        elif args.command == "audit-readiness":
            from .readiness_audit import audit_readiness
            result = audit_readiness(args.intake, args.labels, args.receipt, args.output)
        elif args.command == "prepare-label-revision":
            from .label_revision import prepare_revision
            result = prepare_revision(args.intake, args.old_labels, args.audit, args.output)
        elif args.command == "check-label-revision":
            from .label_revision import check_revision
            result = check_revision(args.artifact)
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
