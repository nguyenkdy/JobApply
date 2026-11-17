"""Unseen titles are metadata, never admission gates or matching shortcuts."""
from copy import deepcopy
from _support import WorkspaceTest
from ml_task_matching.policy import cv_facts, inspect_pair, job_facts, judge, task_evidence


class TaskMatchingTests(WorkspaceTest):
    def payload(self):
        return dict(cv=dict(role="Platform Engineer", text="Tôi triển khai Kubernetes bằng Python."),
            jd=dict(title="Site Reliability Engineer", tasks_text="Triển khai Kubernetes.",
                requirements_text="Must know Kubernetes and Python", preferred_requirements_text=""))

    def test_unseen_titles_allowed_and_no_required_years_needed(self):
        result = inspect_pair(self.payload())
        self.assertEqual(result["decision"]["relevance_0_1_2"], "2")
        self.assertFalse(result["decision"]["title_used_for_decision"])

    def test_title_and_role_renaming_invariant(self):
        payload = self.payload()
        before = inspect_pair(payload)["decision"]
        for cv_role, title in (("", ""), ("Quantum Banana Specialist", "Unknown Position 2050"), ("Backend Python", "Backend Python"), ("Bác sĩ", "Luật sư")):
            payload["cv"]["role"], payload["jd"]["title"] = cv_role, title
            self.assertEqual(inspect_pair(payload)["decision"], before)

    def test_same_title_same_skill_without_task_does_not_match(self):
        payload = self.payload()
        payload["cv"]["text"] = "Python, Kubernetes."
        payload["cv"]["role"] = payload["jd"]["title"] = "DevOps"
        self.assertEqual(inspect_pair(payload)["decision"]["relevance_0_1_2"], "")

    def test_title_only_technology_is_not_used(self):
        payload = self.payload()
        payload["jd"]["requirements_text"] = ""
        payload["jd"]["title"] = "Python Kotlin Developer"
        result = inspect_pair(payload)
        self.assertNotIn("python", result["jd_facts"]["skills"])
        self.assertNotIn("kotlin", result["jd_facts"]["skills"])

    def test_actual_different_task_is_unknown_not_zero(self):
        payload = self.payload()
        payload["cv"]["text"] = "Tôi huấn luyện mô hình bằng Python."
        payload["jd"].update(tasks_text="Xây dựng API.", requirements_text="Must know Python")
        decision = inspect_pair(payload)["decision"]
        self.assertEqual(decision["relevance_0_1_2"], "")
        self.assertEqual(decision["shared_skills"], ["python"])

    def test_nonsoftware_work_not_fabricated_as_supported(self):
        payload = self.payload()
        payload["cv"] = dict(role="Nurse", text="Tôi chăm sóc bệnh nhân và theo dõi huyết áp.")
        self.assertEqual(inspect_pair(payload)["decision"]["relevance_0_1_2"], "")

    def test_action_object_not_bare_tools(self):
        self.assertFalse(task_evidence("Python, Kubernetes, SQL, CI/CD.", "cv_text", "cv")[0])
        self.assertIn("infrastructure_operations", task_evidence("Deploy Kubernetes.", "tasks_text")[0])

    def test_testing_api_is_not_backend_implementation(self):
        functions, _ = task_evidence("Write regression tests for API.", "tasks_text")
        self.assertIn("quality_testing", functions)
        self.assertNotIn("backend_services", functions)

    def test_negative_hypothetical_and_teaching_context(self):
        for text in ("I never deploy Kubernetes.", "Tôi chưa triển khai Kubernetes.", "If needed, deploy Kubernetes.",
                     "Tôi muốn học triển khai Kubernetes.", "I train staff to deploy Kubernetes."):
            self.assertFalse(task_evidence(text, "cv_text", "cv")[0], text)

    def test_future_cv_does_not_claim_completed_work(self):
        text = "I will deploy Kubernetes."
        self.assertFalse(task_evidence(text, "cv_text", "cv")[0])
        self.assertTrue(task_evidence(text, "tasks_text", "jd")[0])

    def test_future_technology_not_present_skill(self):
        payload = self.payload()
        payload["cv"]["text"] += " Tôi sẽ dùng Java."
        payload["jd"]["requirements_text"] += " and Java"
        result = inspect_pair(payload)
        self.assertNotIn("java", result["cv_facts"]["skills"])
        self.assertEqual(result["decision"]["relevance_0_1_2"], "1")

    def test_terminal_preference_not_core_skill(self):
        payload = self.payload()
        payload["jd"].update(tasks_text="Deploy infrastructure.", requirements_text="Experience with Python is a plus")
        self.assertNotIn("python", inspect_pair(payload)["jd_facts"]["skills"])

    def test_paragraph_unconsumed_task_blocks_strong_label(self):
        payload = self.payload()
        payload["jd"]["tasks_text"] = "Triển khai Kubernetes và thiết kế động cơ phản lực."
        result = inspect_pair(payload)
        self.assertEqual(result["decision"]["relevance_0_1_2"], "1")
        self.assertFalse(result["jd_facts"]["task_segments"][0]["bounded_statement_complete"])

    def test_unrecognized_requirement_blocks_two(self):
        payload = self.payload()
        payload["jd"]["requirements_text"] += "\nMust know SecretFramework"
        self.assertEqual(inspect_pair(payload)["decision"]["relevance_0_1_2"], "1")

    def test_empty_requirements_not_assumed_complete(self):
        payload = self.payload()
        payload["jd"]["requirements_text"] = ""
        self.assertEqual(inspect_pair(payload)["decision"]["relevance_0_1_2"], "1")

    def test_optional_years_never_block_by_required_comparison(self):
        payload = self.payload()
        payload["jd"]["preferred_requirements_text"] = "5 years of experience with Python"
        result = inspect_pair(payload)["decision"]
        self.assertEqual(result["relevance_0_1_2"], "2")
        self.assertEqual(result["duration_states"], [])

    def test_unknown_role_explicit_duration_contradiction(self):
        payload = self.payload()
        payload["cv"]["text"] += " Tôi có 12 tháng kinh nghiệm làm việc với Python."
        payload["jd"]["requirements_text"] += "\nAt least 3 years of experience with Python"
        self.assertEqual(inspect_pair(payload)["decision"]["relevance_0_1_2"], "0")

    def test_total_not_converted_to_technology(self):
        payload = self.payload()
        payload["cv"]["text"] += " Tôi có 48 tháng kinh nghiệm làm việc."
        payload["jd"]["requirements_text"] += "\nAt least 3 years of experience with Python"
        decision = inspect_pair(payload)["decision"]
        self.assertEqual(decision["duration_states"][0]["state"], "unknown")
        self.assertEqual(decision["relevance_0_1_2"], "1")

    def test_missing_skill_not_explicit_negative(self):
        payload = self.payload()
        payload["jd"]["requirements_text"] += " and Java"
        self.assertEqual(inspect_pair(payload)["decision"]["relevance_0_1_2"], "1")

    def test_data_analysis_kept_distinct_from_data_pipeline(self):
        functions, _ = task_evidence("Phân tích tỷ lệ khách hàng rời bỏ bằng SQL.", "tasks_text")
        self.assertIn("data_analysis", functions)
        self.assertNotIn("data_pipeline", functions)

    def test_evidence_offsets_preserved_and_inputs_not_mutated(self):
        payload = self.payload()
        before = deepcopy(payload)
        result = inspect_pair(payload)
        for spans in result["cv_facts"]["functions"].values():
            for span in spans:
                self.assertEqual(payload["cv"]["text"][span["start"]:span["end"]], span["quote"])
        self.assertEqual(payload, before)

    def test_frozen_scope_exclusion_preserved_not_new_title_gate(self):
        cv = cv_facts(self.payload()["cv"]["text"])
        jd = job_facts(dict(occurrences=[dict(raw_row=self.payload()["jd"])]))
        jd["outside_scope"] = True
        self.assertEqual(judge(cv, jd)["reason"], "preserved_dataset_scope_exclusion")
