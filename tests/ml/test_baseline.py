"""ML-only tests: run with unittest, without backend/DB dependencies."""
import contextlib
import importlib.util
import io
from pathlib import Path
import shutil
import sys
import unittest
from uuid import uuid4

if any(importlib.util.find_spec(name) is None for name in ("numpy", "sklearn", "joblib")):
    raise unittest.SkipTest("ML tests require the separate requirements-ml-win-py314.lock.txt environment")

PILOT = Path(__file__).resolve().parents[2] / "jobapply_pilot_v1"
sys.path.insert(0, str(PILOT))
from baseline_common import (complete_grid, finite, keyed_rows, macro_metrics, metrics,
                             read_csv, sha256, validate_ranks, write_json, write_table)
from compare_embeddings import split_for_model
from run_baseline import normalize_labels, verify_run
from train_matcher import train, training_rows
from jobapply_experience_v2.run_experiment import gap_features, experience_inputs


class BaselineTests(unittest.TestCase):
    def setUp(self):
        test_root = PILOT.parent / ".test-data" / "ml"
        self.root = test_root / uuid4().hex
        self.root.mkdir(parents=True)

        def cleanup():
            if not self.root.resolve().is_relative_to(test_root.resolve()):
                raise ValueError("Test cleanup escaped its workspace")
            shutil.rmtree(self.root)

        self.addCleanup(cleanup)

    def csv(self, text):
        path = self.root / "input.csv"
        path.write_text(text, encoding="utf-8")
        return path

    def test_reject_malformed_schema_and_rows(self):
        for text in ("cv_id,job_id,\na,b,\n", "cv_id,job_id,job_id\na,b,c\n",
                     "cv_id,job_id\na\n", "cv_id,job_id\na,b,c\n", "cv_id,job_id\n"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                read_csv(self.csv(text))

    def test_reject_duplicate_empty_and_padded_ids(self):
        for text in ("a,b\na,b", ",b", "a, b"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                keyed_rows(self.csv("cv_id,job_id\n" + text + "\n"))

    def test_grid_requires_every_pair_and_known_ids(self):
        complete_grid({("a", "x"), ("a", "y"), ("b", "x"), ("b", "y")})
        with self.assertRaises(ValueError):
            complete_grid({("a", "x"), ("a", "y"), ("b", "x")})
        with self.assertRaises(ValueError):
            complete_grid({("a", "z")}, ["a"], ["x"])

    def test_invalid_scores_are_never_repaired(self):
        for value in ("64.431.045", "nan", "inf", "-inf", "", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                finite(value, "score")

    def test_rank_permutation_and_score_order(self):
        pairs = {("a", "x"): dict(job_id="x", rank="1", score="1"),
                 ("a", "y"): dict(job_id="y", rank="2", score="2")}
        with self.assertRaises(ValueError):
            validate_ranks(pairs, "rank", "score")
        pairs["a", "y"]["rank"] = "1"
        with self.assertRaises(ValueError):
            validate_ranks(pairs, "rank")

    def test_metrics_hand_calculation_and_undefined_counts(self):
        import math
        got = metrics([dict(relevance=v) for v in [1, 2, 0]], 2)
        self.assertEqual(got["recall_at_2"], 1)
        self.assertAlmostEqual(got["ndcg_at_2"], (1 + 3 / math.log2(3)) / (3 + 1 / math.log2(3)))
        empty = metrics([dict(relevance=0)] * 3, 2)
        self.assertEqual(empty, dict(recall_at_2=None, ndcg_at_2=None))
        macro = macro_metrics([got, empty], 2)
        self.assertEqual(macro["recall_at_2_defined_cvs"], 1)
        self.assertEqual(macro["ndcg_at_2_excluded_cvs"], 1)
        for k in (0, 4, -1):
            with self.assertRaises(ValueError):
                metrics([dict(relevance=0)] * 3, k)

    def test_label_normalization_preserves_values_and_no_human_claim(self):
        cvs = read_csv(PILOT / "cvs_synthetic.csv")
        jobs = read_csv(PILOT / "jobs_pilot.csv")
        target = self.root / "normalized.csv"
        normalize_labels(PILOT / "judgments_ai_draft.csv", PILOT / "results/judgments_template.csv", target, cvs, jobs)
        original = read_csv(PILOT / "judgments_ai_draft.csv", allow_legacy_blank=True)
        actual = read_csv(target)
        for before, after in zip(original, actual):
            for key in ("cv_id", "job_id", "relevance_0_1_2", "rationale"):
                self.assertEqual(before[key], after[key])
            self.assertEqual(after["reviewer"], "")
            self.assertEqual(after["annotation_origin"], "ai_draft")
            self.assertEqual(after["label_status"], "needs_review")
        self.assertNotIn(b"\r\n", target.read_bytes())
        self.assertFalse(target.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_small_grid_training_and_fold_isolation(self):
        # 3 CVs x 3 jobs, k=2: catches accidental reintroduction of 6/50/300.
        scores, labels = {}, {}
        for ci, cv in enumerate(("a", "b", "c")):
            for j in range(3):
                key = cv, str(j)
                scores[key] = dict(cv_id=cv, job_id=str(j), bm25_score=str(3-j+ci), cosine=str((3-j)/4),
                                   rank_bm25=str(j+1), rank_embedding=str(j+1))
                labels[key] = dict(relevance_0_1_2=str(2-j))
        rows = training_rows(scores, labels)
        with contextlib.redirect_stdout(io.StringIO()):
            predictions, evaluations = train(rows, self.root / "first", 2)
            changed = [dict(r, relevance=(r["relevance"] + 1) % 3) if r["cv_id"] == "a" else r.copy() for r in rows]
            second, _ = train(changed, self.root / "second", 2)
        # Altering only held-out labels cannot change its model/scaler predictions.
        self.assertEqual([r["match_score"] for r in predictions if r["cv_id"] == "a"],
                         [r["match_score"] for r in second if r["cv_id"] == "a"])
        self.assertEqual(len(evaluations), 9)
        with self.assertRaises(FileExistsError):
            train(rows, self.root / "first", 2)

    def test_unknown_experience_is_not_zero_evidence(self):
        unknown = gap_features([("DevOps", 60, False)], {})
        self.assertIsNone(unknown["gap_months_observed"])
        self.assertEqual(unknown["coverage"], 0)
        known = gap_features([("DevOps", 60, False)], {"DevOps": 24})
        self.assertEqual(known["gap_months_observed"], 36)
        self.assertEqual(known["coverage"], 1)
        self.assertEqual(gap_features([("Python", 36, True)], {"Python": 36})["gap_months_observed"], 1)
        requirements, experience = experience_inputs(PILOT)
        self.assertEqual(len(experience), 6)
        self.assertEqual(sum(bool(v) for v in requirements.values()), 41)

    def test_long_lines_chunk_without_loss(self):
        text = "Python " * 40 + "\nDjango PostgreSQL"
        chunks = split_for_model(text, lambda s: len(s) <= 32)
        self.assertTrue(all(len(s) <= 32 for s in chunks))
        self.assertEqual(" ".join(chunks).split(), text.split())

    def test_manifest_detects_tampering_and_extra_files(self):
        artifact = self.root / "artifact.csv"
        write_table(artifact, [dict(x="1")])
        write_json(self.root / "manifest.json", dict(artifacts={"artifact.csv": dict(sha256=sha256(artifact))}))
        verify_run(self.root)
        artifact.write_text("changed", encoding="utf-8")
        with self.assertRaises(ValueError):
            verify_run(self.root)
        with self.assertRaises(FileExistsError):
            write_table(artifact, [dict(x="2")])


if __name__ == "__main__":
    unittest.main()
