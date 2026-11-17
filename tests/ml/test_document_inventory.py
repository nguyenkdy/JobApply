"""Inventory must distinguish observations from unproven semantic absence."""
from copy import deepcopy
from _support import WorkspaceTest
from ml_readiness.__main__ import contained, duration_status, inspect_record, missing_timeline


class DocumentInventoryTests(WorkspaceTest):
    def record(self, text, kind="cv"):
        return dict(kind=kind, record_id="R", external_id="fixture", group_id="G", text_sha256="fixture",
            text_original=text, occurrences=[dict(raw_row=dict(title_for_matching="Engineer", tasks_text=text,
                requirements_text=text, preferred_requirements_text=""))])

    def facts(self):
        return dict(role="", durations=[], functions={}, skills={}, clauses=[])

    def test_no_numeric_signal_does_not_prove_absence(self):
        self.assertEqual(duration_status("jd", True, 0, 0, 0, False), "no_numeric_cue_detected_absence_not_proven")

    def test_empty_source_distinct_from_extractor_failure(self):
        self.assertEqual(duration_status("jd", False, 0, 0, 0, False), "source_field_empty")
        self.assertEqual(duration_status("jd", True, 0, 1, 1, False), "numeric_cue_without_parsed_scope")

    def test_explicit_unknown_and_numeric_conflict(self):
        self.assertEqual(duration_status("cv", True, 0, 0, 0, True), "source_explicitly_leaves_timeline_unknown")
        self.assertNotEqual(duration_status("cv", True, 0, 1, 1, True), "source_explicitly_leaves_timeline_unknown")

    def test_explicit_missing_timeline_preserves_quote(self):
        text = "Backend\nTôi viết API. Không còn bảng thời gian để khai tổng tháng."
        spans = missing_timeline(text)
        self.assertEqual(len(spans), 1)
        self.assertEqual(text[spans[0]["start"]:spans[0]["end"]], spans[0]["quote"])
        self.assertFalse(missing_timeline("Tôi có 12 tháng làm việc, không đủ thời gian cho dự án phụ."))

    def test_cv_task_cue_offsets_exclude_role_heading(self):
        text = "Backend\nTôi viết API bằng Python. Không còn bảng thời gian để khai tổng tháng."
        row, evidence = inspect_record(self.record(text), self.facts())
        self.assertEqual(row["duration_status"], "source_explicitly_leaves_timeline_unknown")
        self.assertEqual(row["task_functions_parsed"], 0)
        self.assertEqual(row["task_action_cues"], 1)
        for s in evidence["observations"]:
            self.assertEqual(text[s["start"]:s["end"]], s["quote"])

    def test_unknown_scope_numeric_is_candidate_not_requirement(self):
        row, evidence = inspect_record(self.record("3 năm ở vị trí tương tự", "jd"), self.facts())
        self.assertEqual(row["duration_unresolved_cues"], 1)
        self.assertEqual(evidence["observations"][0]["coverage"], "unresolved_candidate")
        self.assertEqual(row["mandatory_clauses"], 0)

    def test_preferred_time_not_counted_as_missed_required_duration(self):
        text = "Ưu tiên có 3 năm kinh nghiệm Python"
        facts = self.facts()
        facts["clauses"] = [dict(state="preferred", evidence=dict(field="requirements_text", start=0, end=len(text), quote=text))]
        row, _ = inspect_record(self.record(text, "jd"), facts)
        self.assertEqual(row["duration_unresolved_cues"], 0)
        self.assertEqual(row["duration_status"], "numeric_cues_only_optional_or_unclassified")

    def test_partial_coverage_not_complete_extraction(self):
        text = "2 years Python; 4 years similar position"
        facts = self.facts()
        facts["clauses"] = [dict(state="duration", evidence=dict(field="requirements_text", start=0, end=14, quote=text[:14]))]
        row, _ = inspect_record(self.record(text, "jd"), facts)
        self.assertEqual(row["duration_status"], "partial_extraction_with_unresolved_cues")

    def test_preferred_field_missing_not_no_preferences_claim(self):
        row, _ = inspect_record(self.record("Python is preferred", "jd"), self.facts())
        self.assertFalse(row["preferred_field_present"])
        self.assertTrue(row["requirements_field_present"])

    def test_source_and_facts_remain_unchanged(self):
        record, facts = self.record("Backend\nTôi sửa API bằng Python."), self.facts()
        before = deepcopy((record, facts))
        inspect_record(record, facts)
        self.assertEqual((record, facts), before)

    def test_same_offsets_in_different_field_do_not_cover_cue(self):
        self.assertFalse(contained(dict(field="tasks_text", start=0, end=2), dict(field="requirements_text", start=0, end=20)))
