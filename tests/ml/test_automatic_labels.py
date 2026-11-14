"""Automatic proxy rules and validators: unknown is not zero; no human gate."""
from copy import deepcopy

from _support import WorkspaceTest
from ml_data.annotation import validate_labels
from ml_data.common import digest, write_csv
from ml_data.extraction import extract_jd_row
from ml_data.label_rules import experience_coverage, label_pair_row
from ml_data.sampling import FIELDS


class AutomaticLabelTests(WorkspaceTest):
    def pair(self):
        cv_text, jd_text = "TEST ONLY CV Python backend for 24 months.", "TEST ONLY JD Python backend requires 24 months."
        return dict(pair_id="TEST_PAIR", partition="train", cv_id="TEST_CV", jd_id="TEST_JD",
                    cv_version=digest(cv_text), jd_version=digest(jd_text), cv_text=cv_text, jd_text=jd_text,
                    label_status="unlabeled", relevance_0_1_2="", cv_evidence="", jd_evidence="", rationale="")

    def records(self):
        cv = dict(role="backend python", skills=["python"], stack=["django"], experience={"backend python": 24},
                  lineage=dict(experience_kind="employment"))
        return cv, deepcopy(cv)

    def test_unknown_role_abstains_and_validation_is_not_complete(self):
        cv, jd = self.records()
        jd["role"] = ""
        base = self.pair()
        labeled = label_pair_row(base, cv, jd)
        self.assertEqual(labeled["relevance_0_1_2"], "")
        self.assertEqual(labeled["label_status"], "insufficient_evidence")
        write_csv(self.folder / "base.csv", [base], FIELDS)
        write_csv(self.folder / "labels.csv", [labeled], FIELDS)
        result = validate_labels(self.folder / "base.csv", self.folder / "labels.csv")
        self.assertTrue(result["valid"])
        self.assertFalse(result["complete"])

    def test_no_unrelated_duration_fallback_or_internship_equivalence(self):
        cv, jd = self.records()
        jd["experience"] = {"react": 6}
        self.assertEqual(experience_coverage(cv, jd), "unknown")
        self.assertEqual(label_pair_row(self.pair(), cv, jd)["relevance_0_1_2"], "1")
        jd["experience"] = {"backend python": 12}
        for kind in ("internship", "project", "unknown"):
            cv["lineage"]["experience_kind"] = kind
            self.assertEqual(experience_coverage(cv, jd), "incomparable")
            self.assertNotEqual(label_pair_row(self.pair(), cv, jd)["relevance_0_1_2"], "2")

    def test_strict_bound_and_no_three_month_slack(self):
        cv, jd = self.records()
        self.assertEqual(label_pair_row(self.pair(), cv, jd)["relevance_0_1_2"], "2")
        receipt = dict(experience_evidence=[dict(scopes=["backend python"], threshold_months=24, strictly_greater=True)])
        self.assertEqual(label_pair_row(self.pair(), cv, jd, receipt)["relevance_0_1_2"], "1")
        jd["experience"] = {"backend python": 27}
        self.assertEqual(label_pair_row(self.pair(), cv, jd)["relevance_0_1_2"], "1")

    def test_duplicate_pairs_and_fabricated_evidence_fail(self):
        base = self.pair()
        cv, jd = self.records()
        labeled = label_pair_row(base, cv, jd)
        write_csv(self.folder / "duplicates.csv", [labeled, labeled], FIELDS)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            validate_labels(self.folder / "duplicates.csv", self.folder / "duplicates.csv")
        write_csv(self.folder / "base.csv", [base], FIELDS)
        labeled["jd_evidence"] = "INVENTED QUOTE"
        write_csv(self.folder / "bad.csv", [labeled], FIELDS)
        with self.assertRaises(ValueError):
            validate_labels(self.folder / "base.csv", self.folder / "bad.csv")

    def test_extraction_does_not_infer_technology_months_or_maximum_as_minimum(self):
        def row(requirement):
            return dict(job_id="TEST_JD", title_for_matching="Backend Python Developer", tasks_text="Build APIs",
                        requirements_text=requirement, preferred_requirements_text="", match_text="TEST ONLY")
        generic = extract_jd_row(row("At least 5 years of software development experience."))
        self.assertEqual(generic["experience"], {"software development": 60})
        specific = extract_jd_row(row("At least 2 years of Python experience."))
        self.assertEqual(specific["experience"], {"python": 24})
        for phrase in ("Up to 3 years of Python experience.", "Ưu tiên 2 năm kinh nghiệm Python.",
                       "3 years software experience and 6 months React experience."):
            self.assertEqual(extract_jd_row(row(phrase))["experience"], {})
