"""Independent fixtures for revised policy; no real CV/JD ranking or count targets."""
from copy import deepcopy
from _support import WorkspaceTest
from ml_data.common import digest
from ml_data.input_contract import contract_entry, verify_execution_contract
from ml_data.readiness_audit import compare_protected, sha_bytes
from ml_data.label_revision import exposure_overlay
from ml_data.technical_policy_v2 import (canon, cv_facts, functions, jd_facts, judge, logic_tree,
                                        mentions, parse_duration, parse_technical, tree_state)


class PolicyV2Tests(WorkspaceTest):
    def job(self, requirements="", tasks="", title="Backend Python", role="backend python"):
        return dict(role=role, role_precision="occupation_rule" if role else "unknown_or_conflicting",
            text_sha256="fixture", benchmark_scope="requires_protocol_mapping",
            occurrences=[dict(raw_row=dict(title_for_matching=title, tasks_text=tasks,
                                           requirements_text=requirements, preferred_requirements_text=""))])

    def cv(self):
        return dict(role="backend python", skills={"python": {}}, functions={}, nonuse={},
                    durations=[dict(scope="python", months=24, kind="employment")])

    def test_aliases_preserve_distinct_languages_and_frameworks(self):
        self.assertEqual(canon("Postgres"), "postgresql")
        self.assertEqual(canon("ReactJS"), "react")
        self.assertNotEqual(canon("React Native"), canon("React"))
        self.assertNotEqual(canon("JavaScript"), canon("Java"))
        self.assertNotEqual(canon(".NET"), canon("ASP.NET Core"))
        hits = mentions("JavaScript, React Native, ASP.NET Core and PostgreSQL")
        self.assertEqual({h[2] for h in hits}, {"javascript", "react native", "asp.net core", "postgresql"})

    def test_parenthesized_logic_respects_nested_alternatives(self):
        tree = logic_tree("(Python hoặc Java) và SQL")
        self.assertEqual(tree_state(tree, {"java", "sql"}, set()), "yes")
        self.assertEqual(tree_state(tree, {"sql"}, {"python"}), "unknown")
        self.assertEqual(tree_state(tree, {"sql"}, {"python", "java"}), "no")
        self.assertIsNone(logic_tree("Python hoặc Java và SQL"))
        self.assertIsNone(logic_tree("Python/Java"))
        self.assertIsNone(logic_tree("Python, Java"))
        self.assertIsNone(logic_tree("Python (or Java"))

    def test_final_and_lists_and_unknown_terms(self):
        tree = logic_tree("Python, SQL and Docker")
        self.assertEqual(tree_state(tree, {"python", "sql"}, set()), "unknown")
        self.assertEqual(tree_state(tree, {"python", "sql", "docker"}, set()), "yes")
        self.assertIsNone(logic_tree("Python and SecretFramework"))
        self.assertEqual(parse_technical("Must know SecretFramework")["state"], "unresolved")

    def test_explicit_one_of_does_not_turn_into_conjunction(self):
        clause = parse_technical("Experience with one of Python, Java")
        self.assertEqual(clause["state"], "mandatory")
        self.assertEqual(tree_state(clause["tree"], {"python"}, {"java"}), "yes")

    def test_complete_vietnamese_and_english_requirements(self):
        for text in ("Có kinh nghiệm với Python và SQL", "Kiến thức vững về Python", "Thành thạo Python & SQL",
                     "Hands-on experience with Python", "Strong knowledge of Python", "Required skills: Python"):
            self.assertEqual(parse_technical(text)["state"], "mandatory", text)
        self.assertEqual(parse_technical("Có kinh nghiệm với Python để phân tích hệ thống")["state"], "unresolved")

    def test_mixed_preference_does_not_drop_mandatory_condition(self):
        self.assertEqual(parse_technical("Must know Python and SQL optional")["state"], "unresolved")
        self.assertEqual(parse_technical("Ưu tiên Python")["state"], "preferred")
        self.assertEqual(parse_technical("Bắt buộc Python", "preferred_requirements_text")["state"], "preferred")
        self.assertEqual(parse_technical("Không yêu cầu Python")["state"], "preferred")

    def test_preferred_heading_controls_following_lines(self):
        facts = jd_facts(self.job("Nice to have:\nExperience with Python\nRequirements:\nExperience with SQL", title="Engineer", role=""))
        self.assertEqual([c["state"] for c in facts["clauses"]], ["preferred", "mandatory"])
        self.assertNotIn("python", facts["skills"])
        self.assertIn("sql", facts["skills"])

    def test_level_and_cross_line_alternatives_cannot_prove_negative(self):
        for text in ("For Lead level:\nAt least 5 years of experience", "Junior:\nAt least 1 year of experience\nSenior:\nAt least 5 years of experience",
                     "One of the following:\nMust know Python\nMust know Java"):
            facts = jd_facts(self.job(text))
            self.assertFalse(any(c["state"] in {"mandatory", "duration"} for c in facts["clauses"]), text)
        self.assertEqual(parse_technical("Must know Python if assigned to backend")["state"], "unresolved")

    def test_duration_aliases_plus_decimal_and_strict_bounds(self):
        expectations = [("Tối thiểu 2 năm kinh nghiệm Python", "python", 24, False),
                        ("2+ years of experience in Software Testing", "kiểm thử phần mềm", 24, False),
                        ("At least 3 years of experience", "professional experience", 36, False),
                        ("More than 1.5 years of experience with Python", "python", 18, True),
                        ("Kinh nghiệm tối thiểu 02 năm kinh nghiệm lập trình", "software development", 24, False)]
        for text, scope, months, strict in expectations:
            value = parse_duration(text)
            self.assertIsNotNone(value, text)
            self.assertEqual((value["scope"], value["months"], value["strict"]), (scope, months, strict))

    def test_range_preserves_upper_uncertainty_and_rejects_bad_ranges(self):
        value = parse_duration("Có từ 1 đến 3 năm kinh nghiệm làm việc với React Native")
        self.assertEqual(value["scope"], "react native")
        self.assertEqual((value["months"], value["range_upper_months"]), (12, 36))
        self.assertTrue(value["upper_interpretation_unresolved"])
        self.assertIsNone(parse_duration("3-1 years of experience"))

    def test_time_is_not_guessed_from_other_role_or_technology(self):
        for text in ("Có 2 năm kinh nghiệm ở vị trí tương tự", "At least 3 years of experience with Python or Java",
                     "Ưu tiên 2 năm kinh nghiệm Python", "At most 2 years of experience", "No experience required",
                     "3+ years developing NodeJS, with TypeScript expertise", "At least ~3 years of experience"):
            self.assertIsNone(parse_duration(text), text)

    def test_same_role_with_exact_scope_can_reach_two(self):
        facts = jd_facts(self.job("Có kinh nghiệm với Python\nTối thiểu 2 năm kinh nghiệm Python"))
        cv = self.cv()
        self.assertEqual(judge(cv, facts)["relevance_0_1_2"], "2")
        cv["durations"][0]["scope"] = "professional experience"
        self.assertEqual(judge(cv, facts)["relevance_0_1_2"], "1")
        cv["durations"][0].update(scope="python", kind="internship")
        self.assertEqual(judge(cv, facts)["relevance_0_1_2"], "1")

    def test_strict_bound_and_explicit_negative_only(self):
        cv = self.cv()
        facts = jd_facts(self.job("More than 2 years of experience with Python"))
        self.assertEqual(judge(cv, facts)["relevance_0_1_2"], "0")
        facts = jd_facts(self.job("Must know Java", title="Backend Java", role="backend java"))
        self.assertEqual(judge(cv, facts)["relevance_0_1_2"], "")
        cv["nonuse"]["java"] = {"quote": "Chưa dùng Java"}
        self.assertEqual(judge(cv, facts)["relevance_0_1_2"], "0")

    def test_different_title_without_task_evidence_never_becomes_zero(self):
        cv = self.cv()
        facts = jd_facts(self.job("Experience with Python", title="QA Engineer", role="qa/testing"))
        self.assertEqual(judge(cv, facts)["relevance_0_1_2"], "")
        cv["functions"] = functions("Write test cases and perform automation testing.", "cv_text")
        facts = jd_facts(self.job("Experience with Python", "Write test cases and run automation testing.", "QA Engineer", "qa/testing"))
        result = judge(cv, facts)
        self.assertEqual(result["relevance_0_1_2"], "1")
        self.assertEqual(result["relation"], "shared_task_function")

    def test_unknown_occupation_needs_positive_task_evidence(self):
        cv = self.cv()
        facts = jd_facts(self.job("Experience with Python", title="Team Leader", role=""))
        self.assertEqual(judge(cv, facts)["relevance_0_1_2"], "")
        cv["functions"] = functions("Develop backend services.", "cv_text")
        facts = jd_facts(self.job("Experience with Python", "Develop backend services.", "Team Leader", ""))
        self.assertEqual(judge(cv, facts)["relevance_0_1_2"], "1")

    def test_function_evidence_skips_negated_tasks_and_not_just_tool_names(self):
        self.assertFalse(functions("I have never developed backend services.", "fixture"))
        self.assertFalse(functions("Python, FastAPI, SQL.", "fixture"))
        text = "Build backend services. Write test cases."
        result = functions(text, "fixture")
        for values in result.values():
            for span in values:
                self.assertEqual(text[span["start"]:span["end"]], span["quote"])

    def test_cv_dotnet_nonuse_and_function_offsets(self):
        text = "Backend Python\nTôi viết API bằng Python. Chưa dùng Node.js."
        span = dict(start=text.index("Python", 15), end=text.index("Python", 15)+6, quote="Python")
        old = dict(role="backend python", skills={"Python": span}, durations=[], nonuse={}, text_sha256=digest(text))
        result = cv_facts(dict(text_original=text), old)
        self.assertIn("node.js", result["nonuse"])
        for values in result["functions"].values():
            for item in values:
                self.assertEqual(text[item["start"]:item["end"]], item["quote"])
        self.assertEqual(old["nonuse"], {})

    def test_not_administering_does_not_mean_never_using_a_technology(self):
        text = "DevOps/Cloud\nChưa quản trị Kubernetes."
        original = dict(role="devops/cloud", skills={}, durations=[], nonuse={}, text_sha256=digest(text))
        result = cv_facts(dict(text_original=text), original)
        self.assertNotIn("kubernetes", result["nonuse"])

    def test_range_upper_uncertainty_blocks_strong_label(self):
        cv = self.cv()
        facts = jd_facts(self.job("Must know Python\n1-3 years of experience with Python"))
        self.assertEqual(judge(cv, facts)["relevance_0_1_2"], "1")
        cv["durations"][0]["months"] = 6
        self.assertEqual(judge(cv, facts)["relevance_0_1_2"], "0")

    def test_occupation_overlay_has_literal_cue_and_preserves_conflicts(self):
        facts = jd_facts(self.job(title="API Integration Engineer", role=""))
        self.assertEqual(facts["role"], "integration engineer")
        self.assertEqual(facts["role_overlay"]["evidence"][0]["quote"], "API Integration Engineer")
        record = self.job(title="Software Engineer (Python + Java)", role="")
        self.assertEqual(jd_facts(record)["role"], "")

    def test_old_and_data_hashes_cannot_be_rebaselined(self):
        path = "jobapply_pilot_v1/evaluate_top5.py"
        before = b"x=1\r\n"
        now = b"x=1\n"
        proof = compare_protected(path, now, sha_bytes(before))
        self.assertEqual(contract_entry(path, now, sha_bytes(before), proof)["accepted_as"], "audited_code_lf_equivalence")
        with self.assertRaisesRegex(ValueError, "mutation"):
            contract_entry(path, b"x=2\n", sha_bytes(before), proof)
        raw_proof = compare_protected("jobs_matching.csv", before, sha_bytes(before))
        with self.assertRaisesRegex(ValueError, "mutation"):
            contract_entry("jobs_matching.csv", now, sha_bytes(before), raw_proof)
        tampered = dict(proof, expected_sha256=sha_bytes(now))
        with self.assertRaisesRegex(ValueError, "reference"):
            contract_entry(path, now, sha_bytes(before), tampered)

    def test_all_siblings_get_development_overlay_without_partition_rewrite(self):
        cvs = {"A": dict(group_id="G"), "B": dict(group_id="G"), "C": dict(group_id="H")}
        assignments = [dict(kind="cv", record_id="A", partition="test"), dict(kind="cv", record_id="B", partition="test"), dict(kind="cv", record_id="C", partition="train")]
        before = deepcopy(assignments)
        overlay = exposure_overlay(cvs, assignments)
        self.assertEqual(overlay["original_partitions"], {"A": "test", "B": "test", "C": "train"})
        self.assertTrue(all(g["effective_exposure"] == "development" and not g["eligible_for_independent_evaluation"] for g in overlay["groups"]))
        self.assertEqual(assignments, before)
        self.assertEqual(overlay["seed_retries"], 0)

    def test_execution_code_uses_canonical_lf_but_rejects_real_edits(self):
        source = b"def fixture():\n    return 1\n"
        saved = {"policy.py": dict(raw_sha256=sha_bytes(source.replace(b"\n", b"\r\n")), lf_sha256=sha_bytes(source))}
        current = {"policy.py": dict(raw_sha256=sha_bytes(source), lf_sha256=sha_bytes(source))}
        self.assertEqual(verify_execution_contract(saved, current)["raw_byte_differences"], ["policy.py"])
        current["policy.py"]["lf_sha256"] = sha_bytes(source.replace(b"1", b"2"))
        with self.assertRaisesRegex(ValueError, "beyond EOL"):
            verify_execution_contract(saved, current)
