"""Offline TEST ONLY fixtures: no encoder download and no benchmark tuning."""
from copy import deepcopy
import math
from unittest.mock import patch

import numpy as np

from _support import WorkspaceTest
from ml_data.common import seal, write_csv, write_json
from ml_experiment.artifacts import environment, load_bundle
from ml_experiment.core import (aggregate, expected_relevance, fit_classifier, metadata_features,
                                professional_view, rank_metrics, select_validation)
from ml_experiment.runner import partition_pairs
from ml_experiment.predict import predict_records, validate_cv


class Step4Tests(WorkspaceTest):
    def record(self):
        return dict(text_normalized="TEST ONLY professional Python text", role="backend python", skills=["python"],
                    stack=["django"], experience={"backend python": 24}, lineage=dict(experience_kind="employment"))

    def test_scope_unknown_gap_and_strictness_are_distinct(self):
        cv, jd = self.record(), self.record()
        jd["experience"] = {"backend python": 36, "react": 12}
        f = metadata_features(cv, jd, {})
        self.assertEqual(f["experience_coverage"], 0.5)
        self.assertEqual(f["experience_gap_years"], 1)
        jd["experience"] = {"backend python": 24}
        f = metadata_features(cv, jd, dict(experience_evidence=[dict(scopes=["backend python"], threshold_months=24, strictly_greater=True)]))
        self.assertEqual(f["experience_gap_years"], 0)
        self.assertEqual(f["strict_bound_violation"], 1)
        cv["lineage"]["experience_kind"] = "internship"
        self.assertEqual(metadata_features(cv, jd, {})["experience_coverage"], 0)
        jd["experience"] = {}
        self.assertEqual(metadata_features(cv, jd, {})["jd_experience_known"], 0)

    def test_personal_metadata_labels_and_ids_cannot_enter_features(self):
        cv, jd = self.record(), self.record()
        altered = deepcopy(cv)
        altered.update(name="TEST NAME", age=99, gender="TEST", address="TEST", record_id="OTHER",
                       relevance_0_1_2=2, label_status="labeled", cv_evidence="TEST ONLY")
        self.assertEqual(professional_view(cv), professional_view(altered))
        self.assertEqual(metadata_features(cv, jd, {}), metadata_features(altered, jd, {}))

    def test_hand_computed_metrics_and_undefined_queries(self):
        ids = [f"j{i}" for i in range(6)]
        metrics = rank_metrics(ids, [2, 1, 0, 0, 0, 0], [6, 5, 4, 3, 2, 1])
        self.assertEqual(metrics["ndcg5"], 1)
        self.assertEqual(metrics["recall5_ge2"], 1)
        opposite = rank_metrics(ids, [2, 1, 0, 0, 0, 0], [1, 2, 3, 4, 5, 6])
        self.assertAlmostEqual(opposite["ndcg5"], (1/math.log2(6)) / (3+1/math.log2(3)))
        self.assertEqual(opposite["recall5_ge2"], 0)
        empty = rank_metrics(ids, [0]*6, list(range(6)))
        self.assertIsNone(empty["ndcg5"])
        partial = rank_metrics(ids, [1]*6, list(range(6)))
        self.assertIsNone(partial["recall5_ge2"])
        self.assertAlmostEqual(partial["recall5_ge1"], 5/6)
        summary = aggregate([metrics, empty, partial])
        self.assertEqual(summary["recall5_ge2_defined"], 1)
        self.assertEqual(summary["recall5_ge2_undefined"], 2)

    def test_ties_use_document_id_and_bad_catalogue_fails(self):
        self.assertEqual(rank_metrics(["f", "e", "d", "c", "b", "a"], [1]*6, [0]*6)["top5"], ["a", "b", "c", "d", "e"])
        with self.assertRaises(ValueError):
            rank_metrics(["x"]*6, [1]*6, [0]*6)
        with self.assertRaises(ValueError):
            rank_metrics(list("abcdef"), [1]*6, [float("nan")]*6)

    def test_scaler_fits_train_only_and_predictions_do_not_mutate_it(self):
        rows = [dict(bm25=x, e5=x/10) for x in range(9)]
        labels = [0]*3+[1]*3+[2]*3
        model = fit_classifier(rows, labels, ["bm25", "e5"], 1)
        np.testing.assert_allclose(model[0].mean_, [4, 0.4])
        mean = model[0].mean_.copy()
        scores = expected_relevance(model, [dict(bm25=999, e5=99)], ["bm25", "e5"])
        self.assertTrue(0 <= scores[0] <= 2)
        np.testing.assert_array_equal(model[0].mean_, mean)
        again = fit_classifier(rows, labels, ["bm25", "e5"], 1)
        np.testing.assert_allclose(model[-1].coef_, again[-1].coef_, atol=1e-12)

    def test_selection_excludes_label_rule_and_uses_declared_ties(self):
        def candidate(name, family, ndcg, complexity, c=0):
            return dict(name=name, family=family, metrics=dict(macro=dict(ndcg5=ndcg, recall5_ge2=0.5)), complexity=complexity, c=c)
        candidates = [candidate("rule_proxy", "rule_proxy", 1, 99), candidate("e5", "e5", 0.8, 2),
                      candidate("lr_text_C1", "text", 0.8, 4, 1), candidate("bm25", "bm25", 0.7, 1)]
        self.assertEqual(select_validation(candidates)["name"], "e5")
        candidates[2]["metrics"]["macro"]["ndcg5"] = 0.9
        self.assertEqual(select_validation(candidates)["name"], "lr_text_C1")

    def test_full_grid_and_label_status_required(self):
        target = self.folder / "validation_labels"
        target.mkdir()
        rows = [dict(cv_id="cv", jd_id=f"jd{i}", partition="validation", label_status="labeled", relevance_0_1_2="1") for i in range(5)]
        write_csv(target / "pairs.csv", rows, tuple(rows[0]))
        self.assertEqual(len(partition_pairs(self.folder, "validation", ["cv"], [f"jd{i}" for i in range(5)])), 5)
        with self.assertRaisesRegex(ValueError, "grid"):
            partition_pairs(self.folder, "validation", ["cv"], [f"jd{i}" for i in range(6)])

    def test_bundle_tampering_rejected_before_pickle_load(self):
        folder = self.folder / "bundle"
        folder.mkdir()
        write_json(folder / "selected.json", dict(name="keyword", family="keyword", features=[]))
        write_json(folder / "environment.json", environment())
        seal(folder, "step4-model", {})
        chosen, estimator = load_bundle(folder)
        self.assertEqual(chosen["name"], "keyword")
        self.assertIsNone(estimator)
        (folder / "selected.json").write_text("{}", encoding="utf-8")
        with patch("joblib.load", side_effect=AssertionError("Must never deserialize")):
            with self.assertRaisesRegex(ValueError, "integrity"):
                load_bundle(folder)

    def test_release_predicts_from_professional_fields_only(self):
        folder = self.folder / "release"
        folder.mkdir()
        write_json(folder / "selected.json", dict(name="keyword", family="keyword", features=[]))
        write_json(folder / "environment.json", environment())
        jobs = [dict(self.record(), record_id=f"JD{i}", external_id=f"job{i}",
                     text_normalized="TEST ONLY " + " ".join(f"tech{i}word{k}" for k in range(30))) for i in range(5)]
        write_json(folder / "catalogue.json", jobs)
        write_json(folder / "jd_receipts.json", {f"job{i}": {} for i in range(5)})
        np.save(folder / "jd_vectors.npy", np.zeros((5, 2)), allow_pickle=False)
        seal(folder, "step4-model", {})
        cv = dict(jobs[2], record_id="CV", text_scope="professional")
        a = predict_records(folder, [cv])
        b = predict_records(folder, [dict(cv, name="TEST PERSON", age=90, gender="TEST")])
        self.assertEqual(a, b)
        self.assertEqual(a[0]["ranking"][0]["jd_id"], "JD2")

    def test_inference_rejects_raw_scope_and_nonfinite_months(self):
        cv = dict(self.record(), text_normalized="TEST ONLY professional text. "*5, text_scope="professional")
        validate_cv(cv)
        with self.assertRaises(ValueError):
            validate_cv(dict(cv, text_scope="raw"))
        with self.assertRaises(ValueError):
            validate_cv(dict(cv, experience={"python": float("nan")}))
