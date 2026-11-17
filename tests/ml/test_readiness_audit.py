"""Audit interpretation tests; never modify the labeling policy or holdout CVs."""
from copy import deepcopy
from _support import WorkspaceTest
from ml_data.readiness_audit import (clause_diagnostic, compare_protected, jd_diagnostics,
                                     pair_diagnostics, positive_two_gaps, sha_bytes, unlabeled_reason)


class ReadinessAuditTests(WorkspaceTest):
    def test_eol_proof_reconstructs_exact_historical_code_hash(self):
        current = b"print('fixture')\n# second line\n"
        expected = current.replace(b"\n", b"\r\n")
        result = compare_protected("jobapply_pilot_v1/evaluate_top5.py", current, sha_bytes(expected))
        self.assertEqual(result["status"], "eol_only_proven")
        self.assertEqual(result["historical_eol"], "CRLF")
        self.assertNotEqual(result["current_sha256"], result["expected_sha256"])
        self.assertEqual(result["canonical_lf_sha256"], sha_bytes(current))
        self.assertEqual(current, b"print('fixture')\n# second line\n")

    def test_real_code_change_and_data_newlines_are_not_excused(self):
        old = b"x=1\r\n"
        result = compare_protected("jobapply_pilot_v1/evaluate_top5.py", b"x=2\n", sha_bytes(old))
        self.assertEqual(result["status"], "unexplained_change")
        result = compare_protected("jobs_matching.csv", b"a,b\n1,2\n", sha_bytes(b"a,b\r\n1,2\r\n"))
        self.assertEqual(result["status"], "unexplained_change")
        self.assertEqual(compare_protected("any.csv", old, sha_bytes(old))["status"], "byte_identical")

    def fixture(self):
        cv = dict(role="backend python", skills={"python": {}})
        jd = dict(role="qa/testing", role_precision="occupation_rule", skills={"java": {}},
                  clauses=[dict(state="unresolved")], unresolved_durations=[dict(quote="unknown")])
        decision = dict(relevance_0_1_2="", reason="insufficient_affirmative_compatibility",
                        relation="different_titles_fit_unresolved", shared_skills=[], mandatory_states=[], duration_states=[])
        return cv, jd, decision

    def test_different_roles_are_policy_uncertainty_not_parser_cause_or_negative(self):
        cv, jd, decision = self.fixture()
        before = deepcopy(decision)
        self.assertEqual(unlabeled_reason(cv, jd, decision), "different_roles_fit_unresolved")
        self.assertEqual(decision, before)
        self.assertEqual(decision["relevance_0_1_2"], "")

    def test_exact_skill_disjointness_is_not_missing_text(self):
        cv, jd, decision = self.fixture()
        decision["relation"] = "same_role_assertion"
        self.assertEqual(unlabeled_reason(cv, jd, decision), "no_exact_shared_skill")
        jd["skills"] = {}
        self.assertEqual(unlabeled_reason(cv, jd, decision), "no_jd_core_skill_evidence")

    def test_role_unknown_generic_and_scope_follow_saved_precedence(self):
        cv, jd, decision = self.fixture()
        decision["reason"] = "unknown_generic_or_conflicting_occupation"
        jd["role"] = ""
        self.assertEqual(unlabeled_reason(cv, jd, decision), "unknown_or_conflicting_jd_role")
        jd.update(role="software developer unspecified", role_precision="generic")
        self.assertEqual(unlabeled_reason(cv, jd, decision), "generic_jd_role")
        decision["reason"] = "outside_software_scope"
        self.assertEqual(unlabeled_reason(cv, jd, decision), "outside_software_scope")
        decision["relevance_0_1_2"] = "0"
        with self.assertRaisesRegex(ValueError, "blank labels"):
            unlabeled_reason(cv, jd, decision)

    def test_positive_two_gaps_overlap_without_creating_new_labels(self):
        _, jd, decision = self.fixture()
        decision.update(relevance_0_1_2="1", relation="potentially_overlapping_functions")
        gaps = positive_two_gaps(jd, decision)
        self.assertEqual(set(gaps), {"role_overlap_not_exact", "no_parsed_mandatory_technology",
            "no_parsed_required_duration", "unresolved_technical_clause", "unresolved_duration_clause"})
        self.assertEqual(decision["relevance_0_1_2"], "1")

    def test_grammar_failure_classifies_mechanism_not_requirement_strength(self):
        examples = [("- Testing tools: Python, SQL", ["python", "sql"], "prefix_not_supported"),
                    ("- Thành thạo Python & SQL", ["python", "sql"], "technology_expression_not_supported"),
                    ("Có kinh nghiệm 2 năm ở vị trí tương tự", [], "duration_sentence_not_supported"),
                    ("Bắt buộc Python", ["python"], "document_guard_disabled_local_parse")]
        for quote, terms, expected in examples:
            clause = dict(state="unresolved", terms=terms, evidence=dict(quote=quote, field="requirements_text"))
            self.assertEqual(clause_diagnostic(clause), expected)
            self.assertEqual(clause["state"], "unresolved")

    def test_pair_counts_reconcile_and_flags_are_separate(self):
        cv, jd, decision = self.fixture()
        rows = [dict(pair_id="P1", partition="train", cv_id="C", jd_id="J", relevance_0_1_2="", reason=decision["reason"], evidence_ref="E1"),
                dict(pair_id="P2", partition="test", cv_id="C", jd_id="J", relevance_0_1_2="1", reason="affirmative_partial_technical_overlap", evidence_ref="E2")]
        evidence = [decision, dict(decision, relevance_0_1_2="1", relation="same_role_assertion")]
        result, diagnoses, gaps, _ = pair_diagnostics(rows, evidence, {"C": cv}, {"C": cv}, {"J": jd})
        self.assertEqual(result["unlabeled_count"], 1)
        self.assertEqual(sum(result["unlabeled_categories_exclusive"].values()), 1)
        self.assertEqual(sum(result["unlabeled_parser_flags_overlapping"].values()), 2)
        self.assertEqual(len(diagnoses), 1)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(result["labels_by_partition"]["test"], {"1": 1})

    def test_nonempty_jd_is_not_declared_missing_when_metadata_unknown(self):
        record = dict(external_id="external-J", skills=[], experience={}, metadata_use_exposure="development",
                      occurrences=[dict(raw_row=dict(title_for_matching="Unmapped profession", tasks_text="Detailed tasks",
                                                    requirements_text="Experience expected", preferred_requirements_text=""))])
        fact = dict(role="", role_precision="unknown_or_conflicting", benchmark_scope="requires_protocol_mapping",
                    skills={}, clauses=[], durations=[], unresolved_durations=[])
        result, table, _, _, _ = jd_diagnostics({"J": record}, {"J": fact}, {"external-J": dict(role_candidates=[])})
        self.assertEqual(result["empty_source_fields"]["requirements_text"], 0)
        self.assertEqual(result["unknown_role_diagnostics"], {"no_candidate_from_extractor": 1})
        self.assertTrue(table[0]["title_nonempty"])
        self.assertEqual(result["jd_without_nonoptional_numeric_duration_pattern"], 1)
