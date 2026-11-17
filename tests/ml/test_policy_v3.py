"""Grammar regressions and real canonical schema shape; no benchmark fitting."""
from copy import deepcopy
from _support import WorkspaceTest

from ml_data import technical_policy_v2 as v2
from ml_data.common import write_csv, write_json
from ml_data.policies import technical_v3 as v3
from ml_data.policies.__main__ import compute


class PolicyV3Tests(WorkspaceTest):
    def facts(self, text):
        record = dict(role="backend python", role_precision="occupation_rule", text_sha256="fixture",
            benchmark_scope="requires_protocol_mapping", occurrences=[dict(raw_row=dict(
                title_for_matching="Backend Python", tasks_text="", requirements_text=text, preferred_requirements_text=""))])
        return v2.jd_facts(record)

    def cv(self):
        return dict(role="backend python", skills={"python": {}}, nonuse={}, functions={},
            durations=[dict(scope="python", months=24, kind="employment")])

    def test_generic_experience_order_not_inferred_from_title(self):
        for text in ("Kinh nghiệm từ 2 năm trở lên", "Kinh nghiệm làm việc từ 2 năm trở lên", "Has 2+ years of experience."):
            result = v3.duration(text)
            self.assertEqual((result["scope"], result["months"]), ("professional experience", 24), text)
        self.assertIsNone(v3.duration("2 năm"))
        self.assertIsNone(v3.duration("2 năm ở vị trí tương đương"))

    def test_professional_technology_full_match(self):
        for text, scope, months in (("You have at least 3 years of professional experience with Python", "python", 36),
            ("Minimum 1 year of professional experience in C++ development.", "c++", 12),
            ("2 years of professional React Native development experience", "react native", 24),
            ("Từ 3 năm kinh nghiệm phát triển phần mềm với công nghệ .NET.", ".net", 36),
            ("Có từ 3 năm kinh nghiệm trở lên lập trình với Java.", "java", 36)):
            result = v3.duration(text)
            self.assertIsNotNone(result, text)
            self.assertEqual((result["scope"], result["months"]), (scope, months), text)

    def test_numbered_bullet_and_decimal(self):
        self.assertEqual(v3.duration("1. Tối thiểu 5 năm kinh nghiệm phát triển phần mềm.")["months"], 60)
        self.assertEqual(v3.duration("1.5 years of experience with Python")["months"], 18)

    def test_duration_preserves_strict_and_range(self):
        self.assertTrue(v3.duration("You have over 2 years of professional experience with Python")["strict"])
        result = v3.duration("Minimum 2-3 years of experience in JavaScript development")
        self.assertEqual((result["months"], result["range_upper_months"]), (24, 36))
        self.assertTrue(result["upper_interpretation_unresolved"])

    def test_duration_rejects_alternatives_qualifiers_and_unknown_scope(self):
        for text in ("3 years of experience with Python or Java", "3 years of experience with Python and SQL",
            "3 years of experience with Python, preferably Django", "3 years of experience with Python if senior",
            "At least ~3 years of experience with Python", "No 3 years of experience with Python required",
            "3 years of experience in a similar position", "3 years of professional experience with SecretFramework"):
            self.assertIsNone(v3.duration(text), text)

    def test_total_never_satisfies_technology_and_internship_not_employment(self):
        jd = v3.jd_facts(self.facts("Must know Python\nYou have at least 3 years of professional experience with Python"))
        cv = self.cv()
        cv["durations"] = [dict(scope="professional experience", months=60, kind="employment")]
        self.assertEqual(v3.judge(cv, jd)["duration_states"][0]["state"], "unknown")
        cv["durations"] = [dict(scope="python", months=6, kind="internship")]
        self.assertEqual(v3.judge(cv, jd)["duration_states"][0]["state"], "unknown")

    def test_full_terminal_preference_and_mixed_guard(self):
        for text in ("Experience with Python is a plus.", "Có kinh nghiệm với Python là một lợi thế."):
            self.assertEqual(v3.parse(text)["state"], "preferred")
        for text in ("Must know Python is a plus", "Có kinh nghiệm Python, SQL là lợi thế",
            "Experience with Python (SQL preferred)", "Experience with Python. Knowledge of SQL is a plus"):
            self.assertFalse(v3.terminal_preference(text), text)

    def test_preference_does_not_supply_core_skill_evidence(self):
        original = self.facts("Experience with Docker is a plus")
        result = v3.jd_facts(original)
        self.assertNotIn("docker", result["skills"])

    def test_complete_new_prefix_does_not_consume_ambiguous_list(self):
        for text in ("Familiarity with Python and SQL", "Nắm vững Python", "Có kiến thức về Python", "Experience using Python"):
            self.assertEqual(v3.parse(text)["state"], "mandatory", text)
        self.assertEqual(v3.parse("Familiarity with Python, SQL")["state"], "unresolved")
        self.assertEqual(v3.parse("Familiarity with Python to build pipelines")["state"], "unresolved")

    def test_sentence_offsets_keep_nodejs_decimal_and_residual(self):
        text = "Must know Node.js. SecretFramework certification required."
        original = self.facts(text)
        result = v3.jd_facts(original)
        self.assertEqual([c["state"] for c in result["clauses"]], ["mandatory", "unresolved"])
        for clause in result["clauses"]:
            span = clause["evidence"]
            self.assertEqual(text[span["start"]:span["end"]], span["quote"])

    def test_cross_sentence_alternative_not_flattened(self):
        for text in ("Experience with Python. Alternatively use Java.", "Experience with Python. Or use Java.",
                     "Must know Python. Not required.", "Must know Python. This is optional."):
            original = self.facts(text)
            self.assertEqual(len(v3.jd_facts(original)["clauses"]), len(original["clauses"]))
            self.assertEqual(v3.jd_facts(original)["clauses"][0]["state"], "unresolved", text)

    def test_unqualified_development_not_automatically_software_scope(self):
        self.assertIsNone(v3.duration("At least 3 years of development experience"))

    def test_inherited_conditional_and_preferred_sections_unchanged(self):
        for text, state in (("Junior:\nExperience with Python\nSenior:\nExperience with Java", "unresolved"),
                            ("Preferred:\nExperience with Python", "preferred")):
            result = v3.jd_facts(self.facts(text))
            self.assertTrue(all(c["state"] == state for c in result["clauses"]))

    def test_bounded_positive_and_explicit_negative_only(self):
        jd = v3.jd_facts(self.facts("Must know Python\nYou have at least 2 years of professional experience with Python"))
        self.assertEqual(v3.judge(self.cv(), jd)["relevance_0_1_2"], "2")
        cv = self.cv()
        cv["durations"][0]["months"] = 6
        self.assertEqual(v3.judge(cv, jd)["relevance_0_1_2"], "0")
        jd["clauses"].append(dict(state="unresolved"))
        self.assertEqual(v3.judge(self.cv(), jd)["relevance_0_1_2"], "1")

    def test_revision_does_not_mutate_parent(self):
        original = self.facts("Familiarity with Python and SQL\nKinh nghiệm từ 2 năm trở lên")
        before = deepcopy(original)
        v3.jd_facts(original)
        self.assertEqual(original, before)

    def test_pair_census_versions_exposure_and_evidence(self):
        folder = self.folder
        write_json(folder / "jd_facts.json", {"J": self.facts("Must know Python\nYou have at least 3 years of professional experience with Python")})
        write_json(folder / "cv_facts.json", {"C": self.cv()})
        old = dict(pair_id="P", cv_id="C", jd_id="J", partition="train", cv_version="cvhash", jd_version="jdhash",
            effective_exposure="development", evaluation_eligible="false", relevance_0_1_2="1", label_status="automatic_rule_proxy", reason="old")
        write_csv(folder / "labels.csv", [old], list(old))
        _, rows, evidence, _, changes, summary = compute(folder)
        self.assertEqual(rows[0]["relevance_0_1_2"], "0")
        self.assertEqual(rows[0]["cv_version"], "cvhash")
        self.assertEqual(rows[0]["partition"], "train")
        self.assertEqual(evidence[0]["duration_states"][0]["state"], "no")
        self.assertTrue(changes)
        self.assertEqual(summary["transitions"], {"1->0": 1})
        self.assertFalse(summary["ready_for_training"])
