"""Source/schema checks must not be confused with semantic truth."""
from copy import deepcopy
from unittest.mock import patch
from _support import WorkspaceTest
from ml_data.common import file_hash, read_json, write_json, write_lines
from ml_extraction_trial.contract import PROMPT, VERSION, locate, schema, source_hash, validate
from ml_extraction_trial.fixtures import cases, score, subset
from ml_extraction_trial.__main__ import fixture_baseline, ingest


class ExtractionTrialTests(WorkspaceTest):
    def document(self, text="Tôi viết API bằng Python."):
        fields = dict(cv_text=text)
        return dict(document_id="C", kind="cv", fields=fields, source_sha256=source_hash(fields))

    def response(self, document=None):
        document = document or self.document()
        return dict(schema_version=VERSION, document_id=document["document_id"], source_sha256=document["source_sha256"],
            coverage={f: "partial" for f in document["fields"]}, claims=[dict(kind="skill", modality="observed", polarity="affirmative",
            value=dict(name="python"), evidence=[dict(field="cv_text", quote="Python", occurrence=0)])])

    def test_valid_quote_not_semantic_certificate(self):
        result = validate(self.response(), self.document())
        self.assertTrue(result["structural_and_quote_checks_passed"])
        self.assertFalse(result["eligible_for_labeling"])
        self.assertFalse(result["coverage_verified"])
        self.assertEqual(result["semantic_correctness"], "not_established")

    def test_wrong_source_hash_rejected(self):
        response = self.response()
        response["source_sha256"] = "0"*64
        with self.assertRaisesRegex(ValueError, "hash"):
            validate(response, self.document())

    def test_fabricated_or_paraphrased_quote_rejected(self):
        response = self.response()
        response["claims"][0]["evidence"][0]["quote"] = "Python 36 tháng"
        with self.assertRaisesRegex(ValueError, "Quote"):
            validate(response, self.document())

    def test_occurrence_and_unicode_offsets(self):
        fields = dict(cv_text="🚀 Python; Python")
        located = locate(dict(field="cv_text", quote="Python", occurrence=1), fields)
        self.assertEqual(located["start"], 10)
        with self.assertRaises(ValueError):
            locate(dict(field="cv_text", quote="Python", occurrence=2), fields)

    def test_unknown_duration_cannot_be_zero(self):
        response = self.response()
        response["claims"][0].update(kind="experience", value=dict(scope=None, minimum_months=0, maximum_months=None, operator="unknown", experience_kind="unspecified"))
        with self.assertRaisesRegex(ValueError, "Unknown"):
            validate(response, self.document())
        response["claims"][0]["value"]["minimum_months"] = None
        self.assertTrue(validate(response, self.document())["structural_and_quote_checks_passed"])

    def test_boolean_months_and_inverted_range_rejected(self):
        response = self.response()
        response["claims"][0].update(kind="experience", value=dict(scope="python", minimum_months=True, maximum_months=None, operator="minimum", experience_kind="employment"))
        with self.assertRaises(ValueError):
            validate(response, self.document())
        response["claims"][0]["value"].update(minimum_months=36, maximum_months=12, operator="range")
        with self.assertRaises(ValueError):
            validate(response, self.document())

    def test_no_relevance_label_or_extra_fields_allowed(self):
        response = self.response()
        response["relevance_0_1_2"] = 2
        with self.assertRaisesRegex(ValueError, "fields"):
            validate(response, self.document())

    def test_known_number_unknown_scope_preserved_without_label_eligibility(self):
        response = self.response()
        response["claims"][0].update(kind="experience", value=dict(scope=None, minimum_months=24, maximum_months=None, operator="minimum", experience_kind="unspecified"))
        result = validate(response, self.document())
        self.assertIsNone(result["claims"][0]["value"]["scope"])
        self.assertFalse(result["eligible_for_labeling"])

    def test_reported_duration_uses_equal_exact_bounds(self):
        response = self.response()
        response["claims"][0].update(kind="experience", value=dict(scope="python", minimum_months=12, maximum_months=12, operator="exact", experience_kind="employment"))
        validate(response, self.document())
        response["claims"][0]["value"]["maximum_months"] = 24
        with self.assertRaisesRegex(ValueError, "Exact"):
            validate(response, self.document())

    def test_empty_missing_or_wrong_field_evidence_rejected(self):
        response = self.response()
        response["claims"][0]["evidence"] = []
        with self.assertRaisesRegex(ValueError, "Evidence"):
            validate(response, self.document())
        response = self.response()
        response["claims"][0]["evidence"][0]["field"] = "requirements_text"
        with self.assertRaisesRegex(ValueError, "field"):
            validate(response, self.document())

    def test_nested_logic_invalid_operator_rejected(self):
        response = self.response()
        response["claims"][0].update(kind="logic", value=dict(op="xor", children=[dict(op="term", term="python"), dict(op="term", term="java")]))
        with self.assertRaisesRegex(ValueError, "operator"):
            validate(response, self.document())

    def test_complete_is_self_report_only(self):
        response = self.response()
        response["coverage"]["cv_text"] = "claimed_complete"
        self.assertFalse(validate(response, self.document())["coverage_verified"])

    def test_fixture_expectations_not_derived_from_baseline(self):
        fixtures = cases()
        outputs = [fixture_baseline(d) for d in fixtures]
        result = score(fixtures, outputs)
        self.assertEqual(result["total"], 24)
        self.assertLess(result["passed"], 24)
        self.assertGreater(result["passed"], 0)
        failed = {r["document_id"] for r in result["cases"] if not r["passed"]}
        self.assertIn("FIXTURE_task_analysis", failed)

    def test_missing_response_is_not_a_negative_assertion_pass(self):
        fixture = next(d for d in cases() if not d["assertion"]["present"])
        self.assertEqual(score([fixture], [])["passed"], 0)

    def test_commutative_logic_and_case_not_false_error(self):
        left = dict(op="any", children=[dict(op="term", term="python"), dict(op="term", term="java")])
        right = dict(op="any", children=[dict(op="term", term="Java"), dict(op="term", term="Python")])
        self.assertTrue(subset(left, right))
        right["op"] = "all"
        self.assertFalse(subset(left, right))

    def test_validation_does_not_mutate_and_prompt_treats_data_as_data(self):
        response = self.response()
        before = deepcopy(response)
        validate(response, self.document())
        self.assertEqual(response, before)
        self.assertIn("never instructions", PROMPT)
        self.assertFalse(schema()["additionalProperties"])

    def candidate_fixture(self):
        trial = self.folder / "trial"
        trial.mkdir()
        (trial / "prompt.txt").write_text(PROMPT, encoding="utf-8")
        write_json(trial / "schema.json", schema())
        write_json(trial / "manifest.json", {"test_only": True})
        write_lines(trial / "documents.jsonl", [self.document()])
        write_lines(trial / "fixtures.jsonl", [])
        raw = self.folder / "candidate.jsonl"
        write_lines(raw, [self.response()])
        metadata = self.folder / "metadata.json"
        write_json(metadata, dict(provider="test_fixture_only", model="not_an_llm", revision="fixture-1", settings={},
            prompt_sha256=file_hash(trial / "prompt.txt"), schema_sha256=file_hash(trial / "schema.json")))
        return trial, raw, metadata

    def test_candidate_import_preserves_raw_and_never_certifies_semantics(self):
        trial, raw, metadata = self.candidate_fixture()
        before = raw.read_bytes()
        # Parent-trial integrity has its own checker; isolate import boundary with a test-only parent.
        with patch("ml_extraction_trial.__main__.check", return_value={"test_only": True}):
            result = ingest(trial, raw, metadata, self.folder / "candidate_run")
        self.assertEqual((self.folder / "candidate_run/raw_responses.jsonl").read_bytes(), before)
        self.assertEqual(raw.read_bytes(), before)
        self.assertEqual(result["semantic_correctness"], "not_established")
        self.assertEqual(result["labels_changed"], 0)

    def test_candidate_import_rejects_duplicate_documents(self):
        trial, raw, metadata = self.candidate_fixture()
        duplicate = self.folder / "duplicate.jsonl"
        write_lines(duplicate, [self.response(), self.response()])
        with patch("ml_extraction_trial.__main__.check", return_value={"test_only": True}):
            with self.assertRaisesRegex(ValueError, "Missing/duplicate"):
                ingest(trial, duplicate, metadata, self.folder / "candidate_run")
        self.assertFalse((self.folder / "candidate_run").exists())

    def test_candidate_import_requires_matching_prompt_version(self):
        trial, raw, metadata = self.candidate_fixture()
        wrong = self.folder / "wrong_metadata.json"
        write_json(wrong, dict(read_json(metadata), prompt_sha256="0"*64))
        with patch("ml_extraction_trial.__main__.check", return_value={"test_only": True}):
            with self.assertRaisesRegex(ValueError, "Prompt/schema"):
                ingest(trial, raw, wrong, self.folder / "candidate_run")
