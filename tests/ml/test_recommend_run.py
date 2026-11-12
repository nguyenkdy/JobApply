"""TEST ONLY tiny fitted models/labels; encoder mocked, no network or real reviewer judgments."""
import importlib.util
import json
import shutil
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from _support import PILOT, WorkspaceTest

if any(importlib.util.find_spec(name) is None for name in ("numpy", "sklearn", "joblib")):
    raise unittest.SkipTest("Run model tests in the separate ML environment")

import joblib
import numpy as np
from baseline_common import sha256, write_json, write_table
from compare_embeddings import MODEL, REVISION
from jobapply_experience_v2.recommend import recommend
from jobapply_experience_v2.run_experiment import EXPERIENCE_FEATURES
from run_artifacts import load_experience_run
from train_matcher import fit_classifier


class RecommendationTests(WorkspaceTest):
    def setUp(self):
        super().setUp()
        self.run = self.make_run("run_A")
        self.env = patch("run_artifacts.environment", return_value=dict(python="TEST_ONLY", lock_sha256="TEST_LOCK"))
        self.env.start(); self.addCleanup(self.env.stop)

    def seal(self, folder):
        path = folder / "manifest.json"
        manifest = dict(status="complete", config=json.loads((folder / "config.json").read_text()),
                        fixture="TEST ONLY fabricated model/labels, not a scientific run",
                        artifacts={p.relative_to(folder).as_posix(): dict(sha256=sha256(p))
                                   for p in folder.rglob("*") if p.is_file() and p != path})
        path.write_text(json.dumps(manifest), encoding="utf-8")

    def make_run(self, name):
        folder = self.folder / name
        (folder / "inputs/jobapply_experience_v2").mkdir(parents=True)
        (folder / "experience_v2").mkdir()
        (folder / "source/jobapply_experience_v2").mkdir(parents=True)
        for file in ("run_bm25.py", "compare_embeddings.py", "encoder.lock.json", "jobapply_experience_v2/run_experiment.py"):
            shutil.copyfile(PILOT / file, folder / "source" / file)
        (folder / "source/requirements-ml-win-py314.lock.txt").write_text("# TEST ONLY; environment validation mocked\n")
        jobs = [dict(job_id=f"j{i}", title_for_matching=f"{name} job {i}", requirements_text="Need DevOps 60 months",
                     match_text="Build Python services. Need DevOps 60 months") for i in range(6)]
        cvs = [dict(cv_id=f"c{i}", cv_text="Python DevOps engineer 24 months", professional_summary="DevOps engineer 24 months",
                    experience_months="24") for i in range(2)]
        write_table(folder / "inputs/jobs_pilot.csv", jobs)
        write_table(folder / "inputs/cvs_synthetic.csv", cvs)
        write_table(folder / "inputs/jobapply_experience_v2/jd_experience.csv", [dict(job_id=r["job_id"], scope="DevOps",
                    threshold_months="60", strictly_greater="0", evidence="Need DevOps 60 months") for r in jobs])
        write_table(folder / "inputs/jobapply_experience_v2/cv_experience.csv", [dict(cv_id=r["cv_id"], scope="DevOps",
                    months="24", evidence="DevOps engineer 24 months") for r in cvs])
        write_json(folder / "config.json", dict(k=5, cv_count=2, job_count=6, features=dict(experience_classifier=list(EXPERIENCE_FEATURES)),
                   bm25=dict(k1=1.5, b=0.75, query_terms="unique", tie_break="job_id ascending")))
        lock = json.loads((folder / "source/encoder.lock.json").read_text())
        write_json(folder / "encoder.json", dict(model=MODEL, revision=REVISION, device="cpu", max_seq_length=512,
                   query_prefix="query: ", passage_prefix="passage: ", batch_size=4,
                   pooling="normalized chunks; token-weighted mean; L2 normalization", torch_threads=1, seed=0,
                   deterministic_algorithms=True, score_decimals=6, files=lock["files"]))
        write_json(folder / "environment.json", dict(python="TEST_ONLY", lock_sha256="TEST_LOCK"))
        (folder / "labels_ai_draft.normalized.csv").write_text("TEST ONLY fabricated labels, not human review\n")
        scores = [dict(cv_id=c["cv_id"], job_id=j["job_id"], bm25_score=(i+1)/2, cosine=(i+1)/10)
                  for c in cvs for i, j in enumerate(jobs)]
        write_table(folder / "embedding_vs_bm25.csv", scores)
        x = np.array([[r["bm25_score"], r["cosine"], 1, 3] for r in scores])
        labels = [i % 3 for i in range(len(scores))]
        if name == "run_B":
            labels = [2-y for y in labels]
        bundle = dict(version=2, mode="full", features=list(EXPERIENCE_FEATURES), pipeline=fit_classifier(x, labels),
                      fixture="TEST ONLY fabricated model",
                      provenance={key: sha256(folder / file) for key, file in {
                          "config_sha256": "config.json", "labels_sha256": "labels_ai_draft.normalized.csv",
                          "scores_sha256": "embedding_vs_bm25.csv", "encoder_sha256": "encoder.json", "environment_sha256": "environment.json"}.items()})
        bundle["provenance"]["code"] = {p.relative_to(folder / "source").as_posix(): sha256(p)
                                         for p in (folder / "source").rglob("*") if p.is_file()}
        joblib.dump(bundle, folder / "experience_v2/experience_classifier.joblib")
        self.seal(folder)
        return folder

    def mock_generate(self, jobs, queries, lexical, **kwargs):
        self.assertTrue(kwargs["local_files_only"])
        self.assertTrue(kwargs["lock_path"].is_file())
        return [dict(cv_id=cv["cv_id"], job_id=j["job_id"], bm25_score=(i+1)/2, cosine=(i+1)/10)
                for cv in queries for i, j in enumerate(jobs)], {}

    def args(self, folder=None):
        return SimpleNamespace(run_dir=folder or self.run, cv_id="c0", cv_text=None, months=None)

    def test_selects_model_catalogue_and_notes_from_requested_run(self):
        second = self.make_run("run_B")
        with patch("jobapply_experience_v2.recommend.generate", side_effect=self.mock_generate) as encoder:
            a = recommend(self.args()); b = recommend(self.args(second))
        self.assertEqual(a["model_sha256"], sha256(self.run / "experience_v2/experience_classifier.joblib"))
        self.assertEqual(b["model_sha256"], sha256(second / "experience_v2/experience_classifier.joblib"))
        self.assertNotEqual(a["model_sha256"], b["model_sha256"])
        self.assertTrue(all(r["title"].startswith("run_B") for r in b["items"]))
        self.assertNotEqual([r["job_id"] for r in a["items"]], [r["job_id"] for r in b["items"]])
        self.assertEqual(a["top_k"], 5)
        self.assertTrue(all(r["gap_months_observed"] == 36 for r in a["items"]))
        self.assertEqual(encoder.call_args.kwargs["lock_path"], second / "source/encoder.lock.json")

    def test_missing_or_modified_artifact_rejected_before_deserialization(self):
        path = self.run / "experience_v2/experience_classifier.joblib"
        path.write_bytes(path.read_bytes() + b"TAMPER")
        with patch("joblib.load") as loader, self.assertRaises(ValueError):
            load_experience_run(self.run)
        loader.assert_not_called()
        path.unlink()
        with patch("joblib.load") as loader, self.assertRaises(OSError):
            load_experience_run(self.run)
        loader.assert_not_called()

    def test_rejects_incomplete_manifest_and_missing_declared_requirements(self):
        path = self.run / "manifest.json"
        manifest = json.loads(path.read_text()); manifest["status"] = "failed"; path.write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            load_experience_run(self.run)
        (self.run / "source/encoder.lock.json").unlink(); self.seal(self.run)
        with self.assertRaises(ValueError):
            load_experience_run(self.run)

    def test_feature_order_and_model_provenance_are_checked(self):
        path = self.run / "experience_v2/experience_classifier.joblib"
        bundle = joblib.load(path); bundle["features"] = list(reversed(bundle["features"])); joblib.dump(bundle, path); self.seal(self.run)
        with self.assertRaisesRegex(ValueError, "feature order"):
            load_experience_run(self.run)
        bundle["features"] = list(EXPERIENCE_FEATURES); bundle["provenance"]["scores_sha256"] = "wrong"
        joblib.dump(bundle, path); self.seal(self.run)
        with self.assertRaisesRegex(ValueError, "provenance"):
            load_experience_run(self.run)

    def test_preprocessing_and_environment_incompatibility_rejected(self):
        source = self.run / "source/run_bm25.py"
        source.write_text(source.read_text().replace("k1=1.5", "k1=1.6"), encoding="utf-8"); self.seal(self.run)
        with self.assertRaisesRegex(ValueError, "Preprocessing incompatible"):
            load_experience_run(self.run)
        with patch("run_artifacts.environment", side_effect=ValueError("incompatible environment")), self.assertRaisesRegex(ValueError, "environment"):
            load_experience_run(self.run)

    def test_new_cv_not_in_training_and_unknown_months(self):
        args = self.args(); args.cv_id = None; args.cv_text = self.folder / "new_cv.TEST_ONLY.txt"
        args.cv_text.write_text("TEST ONLY new anonymized Python engineer profile", encoding="utf-8")
        with patch("jobapply_experience_v2.recommend.generate", side_effect=self.mock_generate):
            result = recommend(args)
        self.assertEqual(result["cv_id"], "NEW_CV")
        self.assertTrue(all(r["gap_months_observed"] is None and r["coverage"] == 0 and r["gap_years_input"] == 0 for r in result["items"]))
        args.months = self.folder / "months.json"; args.months.write_text('{"DevOps": true}')
        with self.assertRaises(ValueError):
            recommend(args)

    def test_existing_cv_rejects_external_month_override(self):
        args = self.args(); args.months = self.folder / "untrusted_months.json"
        with self.assertRaisesRegex(ValueError, "only for a new"):
            recommend(args)
