"""Independent tiny fixtures for proxy semantics; never tune on authored holdout CVs."""
from copy import deepcopy
from _support import WorkspaceTest
from ml_data.common import digest, write_csv, write_lines
from ml_data.expanded_labels import (cv_facts, duration_clause, explicit_nonuse, expected_pairs, jd_facts,
                                     judge, mandatory_clause, tally)


class ExpandedLabelTests(WorkspaceTest):
    def facts(self):
        cv = dict(role="backend python", skills={"python": {}}, nonuse={},
                  durations=[dict(scope="python", months=24, kind="employment")])
        jd = dict(role="backend python", role_precision="occupation_rule", role_evidence=[dict(quote="Python Backend")],
                  benchmark_scope="requires_protocol_mapping", skills={"python": {}},
                  clauses=[mandatory_clause("Bắt buộc Python", ["python"])],
                  durations=[dict(scope="python", months=24, strict=False)], unresolved_durations=[])
        return cv, jd

    def test_missing_skill_is_not_explicit_negative(self):
        cv, jd = self.facts()
        cv["skills"] = {}
        result = judge(cv, jd)
        self.assertEqual(result["relevance_0_1_2"], "")
        self.assertEqual(result["label_status"], "insufficient_evidence")
        cv["nonuse"] = {"python": dict(quote="Chưa dùng Python")}
        self.assertEqual(judge(cv, jd)["relevance_0_1_2"], "0")

    def test_no_negative_from_title_mismatch(self):
        cv, jd = self.facts()
        cv["role"] = "qa/testing"
        self.assertEqual(judge(cv, jd)["relevance_0_1_2"], "")
        cv["role"] = "fullstack"
        self.assertEqual(judge(cv, jd)["relevance_0_1_2"], "1")

    def test_unknown_or_outside_occupation_abstains_even_with_contradiction(self):
        cv, jd = self.facts()
        cv["durations"][0]["months"] = 1
        for update in (dict(role=""), dict(role_precision="generic"), dict(benchmark_scope="outside_software_benchmark")):
            self.assertEqual(judge(cv, dict(jd, **update))["relevance_0_1_2"], "")

    def test_optional_and_ambiguous_logic_cannot_justify_negative(self):
        for quote in ("Ưu tiên Python", "Không bắt buộc Python", "Python là một lợi thế", "Python/Java",
                      "Bắt buộc Python hoặc Java và SQL", "Thành thạo Python khi cần xử lý báo cáo"):
            self.assertNotEqual(mandatory_clause(quote, ["python", "java", "sql"])["state"], "mandatory")
        self.assertEqual(mandatory_clause("Bắt buộc Python", ["python"], "preferred_requirements_text")["state"], "preferred")

    def test_and_or_require_evidence_for_correct_operands(self):
        cv, jd = self.facts()
        cv["skills"] = {}
        cv["nonuse"] = {"python": {}}
        jd["clauses"] = [mandatory_clause("Bắt buộc Python hoặc Java", ["python", "java"])]
        self.assertEqual(judge(cv, jd)["mandatory_states"][0]["state"], "unknown")
        cv["nonuse"]["java"] = {}
        self.assertEqual(judge(cv, jd)["relevance_0_1_2"], "0")
        cv["skills"] = {"java": {}}
        cv["nonuse"].pop("java")
        self.assertEqual(judge(cv, jd)["mandatory_states"][0]["state"], "yes")
        jd["clauses"] = [mandatory_clause("Bắt buộc Python và Java", ["python", "java"])]
        self.assertEqual(judge(cv, jd)["relevance_0_1_2"], "0")

    def test_duration_is_exact_scope_and_professional_only(self):
        cv, jd = self.facts()
        self.assertEqual(judge(cv, jd)["relevance_0_1_2"], "2")
        cv["durations"][0]["scope"] = "professional experience"
        self.assertEqual(judge(cv, jd)["relevance_0_1_2"], "1")
        cv["durations"][0].update(scope="python", kind="project", months=60)
        self.assertEqual(judge(cv, jd)["relevance_0_1_2"], "1")
        cv["durations"][0].update(kind="employment", months=24)
        jd["durations"][0]["strict"] = True
        self.assertEqual(judge(cv, jd)["relevance_0_1_2"], "0")
        cv["durations"][0]["months"] = 25
        self.assertEqual(judge(cv, jd)["relevance_0_1_2"], "2")

    def test_complete_duration_clause_and_no_similar_role_fallback(self):
        self.assertEqual(duration_clause("- Tối thiểu 2 năm kinh nghiệm Python"), dict(scope="python", months=24, strict=False))
        self.assertEqual(duration_clause("More than 24 months of professional experience")["strict"], True)
        for text in ("Có 2 năm kinh nghiệm ở vị trí tương tự", "Ưu tiên 2 năm kinh nghiệm Python", "Dưới 2 năm kinh nghiệm Python",
                     "Tối thiểu 2 năm kinh nghiệm Python hoặc Java", "Tối thiểu 0 tháng kinh nghiệm Python"):
            self.assertIsNone(duration_clause(text))

    def test_nonuse_is_whole_clause_not_omission_or_conditional(self):
        text = "Python đã dùng. Chưa sử dụng Selenium; tôi kiểm thủ công. Tôi chưa dùng Java. Nếu chưa dùng SQL thì học tiếp."
        found = explicit_nonuse(text, ["python", "selenium", "java", "sql"])
        self.assertEqual(set(found), {"selenium", "java"})
        for span in found.values():
            self.assertEqual(text[span["start"]:span["end"]], span["quote"])

    def test_unknown_duration_and_unresolved_clauses_cap_positive(self):
        cv, jd = self.facts()
        jd["unresolved_durations"] = [dict(quote="similar role")]
        self.assertEqual(judge(cv, jd)["relevance_0_1_2"], "1")
        jd["unresolved_durations"] = []
        jd["clauses"].append(dict(state="unresolved", terms=["sql"]))
        self.assertEqual(judge(cv, jd)["relevance_0_1_2"], "1")

    def test_real_jd_schema_offsets_and_cross_line_alternatives(self):
        quote = "Bắt buộc Python"
        record = dict(external_id="J", role="backend python", role_precision="occupation_rule", text_sha256="hash",
                      benchmark_scope="requires_protocol_mapping", occurrences=[dict(raw_row=dict(requirements_text=quote))])
        span = dict(field="requirements_text", start=0, end=len(quote), quote=quote)
        receipt = dict(job_id="J", role_evidence=[], skill_evidence={}, requirement_clauses=[dict(span, terms=["python"])])
        result = jd_facts(record, receipt)
        self.assertEqual(result["clauses"][0]["state"], "mandatory")
        record["occurrences"][0]["raw_row"]["requirements_text"] += "\nNếu ứng viên chọn nhóm khác thì điều kiện thay đổi."
        self.assertEqual(jd_facts(record, receipt)["clauses"][0]["state"], "unresolved")
        broken = deepcopy(receipt)
        broken["requirement_clauses"][0]["start"] = 1
        with self.assertRaisesRegex(ValueError, "literal evidence"):
            jd_facts(record, broken)

    def test_cv_literal_claims_must_match_imported_metadata(self):
        text = "Tôi dùng Python."
        span = dict(start=0, end=len(text), quote=text)
        record = dict(external_id="C", text_original=text, role="backend python", skills=["python"], experience={},
                      text_sha256=digest(text), lineage=dict(experience_kind="unknown"))
        receipt = dict(cv_id="C", text_sha256=digest(text), skills={"Python": span}, durations=[])
        self.assertEqual(set(cv_facts(record, receipt, ["python"])["skills"]), {"python"})
        record["experience"] = {"python": 0}
        with self.assertRaisesRegex(ValueError, "duration metadata"):
            cv_facts(record, receipt, ["python"])

    def test_census_covers_every_jd_while_train_stays_sampled(self):
        (self.folder / "train_candidates").mkdir()
        write_csv(self.folder / "train_candidates/pairs.csv", [dict(partition="train", cv_id="C1", jd_id="J2")], ("partition", "cv_id", "jd_id"))
        write_lines(self.folder / "assignments.jsonl", [dict(kind="cv", record_id="C1", partition="train"),
            dict(kind="cv", record_id="C2", partition="validation"), dict(kind="cv", record_id="C3", partition="test"),
            dict(kind="cv", record_id="OLD", partition="development")])
        result = expected_pairs(self.folder, {"J1": {}, "J2": {}, "J3": {}})
        self.assertEqual(len(result), 7)
        self.assertEqual(sum(p == "train" for p, _, _ in result), 1)
        self.assertFalse(any(c == "OLD" for _, c, _ in result))

    def test_missing_labels_block_full_catalogue_metrics(self):
        rows = [dict(partition="test", cv_id="C", jd_id="J", relevance_0_1_2="", reason="missing")]
        result = tally(rows, {"C": dict(role="backend python")}, {"J": dict(role="")})
        self.assertEqual(result["labels"], {"unlabeled": 1})
        self.assertFalse(result["full_catalogue_ranking_metrics_allowed"])
        self.assertFalse(result["ready_for_training"])
