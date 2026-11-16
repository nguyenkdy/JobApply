"""Top 5 offline demo from a verified completed baseline run; no legacy fallback."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from threadpoolctl import threadpool_limits

from baseline_common import sha256, write_json
from compare_embeddings import generate
from run_artifacts import load_experience_run
from run_bm25 import run
from jobapply_experience_v2.run_experiment import EXPERIENCE_FEATURES, pair_features


def recommend(args):
    context = load_experience_run(args.run_dir)
    folder, jobs, cvs = context['folder'], context['jobs'], context['cvs']
    if args.cv_id:
        if args.months:
            raise ValueError('--months is only for a new --cv-text; synthetic CV uses run annotations')
        cv = next((r for r in cvs if r['cv_id'] == args.cv_id), None)
        if cv is None:
            raise ValueError('Unknown CV ID in selected run')
        selected_id = cv['cv_id']
        months = context['experience'][selected_id]
        # Preserve the baseline query batch shape for synthetic regression checks.
        queries = cvs
    else:
        text = args.cv_text.read_text(encoding='utf-8-sig').strip()
        if not text:
            raise ValueError('Professional CV text is empty')
        selected_id = 'NEW_CV'
        queries = [dict(cv_id=selected_id, cv_text=text)]
        months = json.loads(args.months.read_text(encoding='utf-8-sig')) if args.months else {}
    if not isinstance(months, dict) or any(not isinstance(k, str) or not k.strip() or type(v) is not int or v < 0
                                            for k, v in months.items()):
        raise ValueError('Months must be non-negative integers by documented scope')
    lexical, _ = run(jobs, queries, top_k=5)
    scores, _ = generate(jobs, queries, lexical, local_files_only=True,
                         lock_path=folder / 'source/encoder.lock.json')
    score_by_id = {r['job_id']: r for r in scores if r['cv_id'] == selected_id}
    if set(score_by_id) != {r['job_id'] for r in jobs}:
        raise ValueError('Incomplete retrieval scores')
    features = [pair_features(score_by_id[r['job_id']], context['requirements'][r['job_id']], months) for r in jobs]
    x = np.asarray([[row[key] for key in EXPERIENCE_FEATURES] for row in features])
    if not np.isfinite(x).all():
        raise ValueError('Non-finite inference feature')
    model = context['bundle']['pipeline']
    with threadpool_limits(limits=1):
        predicted = model.predict_proba(x) @ model.classes_
    if not np.isfinite(predicted).all():
        raise ValueError('Non-finite model output')
    order = sorted(range(len(jobs)), key=lambda i: (-predicted[i], jobs[i]['job_id']))
    return dict(run_dir=str(folder), run_manifest_sha256=sha256(folder / 'manifest.json'),
                model_sha256=sha256(folder / 'experience_v2/experience_classifier.joblib'),
                cv_id=selected_id, scope='pilot demo, refit model; not held-out evaluation or live jobs',
                score_type='expected AI-draft relevance on 0..2; not a probability of hiring', top_k=5,
                items=[dict(rank=rank, job_id=jobs[i]['job_id'], title=jobs[i]['title_for_matching'],
                            score=float(predicted[i]), **features[i]) for rank, i in enumerate(order[:5], 1)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True, help='Completed trusted local baseline run')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--cv-id')
    group.add_argument('--cv-text', type=Path, help='New anonymized professional text, not necessarily in training')
    parser.add_argument('--months', type=Path, help='Optional JSON scope -> documented months; omitted means unknown')
    parser.add_argument('--output', type=Path, help='New JSON file outside the immutable run')
    args = parser.parse_args()
    try:
        if args.output and (args.output.resolve().is_relative_to(args.run_dir.resolve()) or args.output.exists()):
            raise ValueError('Output must be a new file outside the immutable run')
        result = recommend(args)
        if args.output:
            write_json(args.output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'Demo error: {exc}\n')


if __name__ == '__main__':
    main()
