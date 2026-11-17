"""Unit tests for additive task-and-requirement matching policy v5."""
from copy import deepcopy
from _support import WorkspaceTest
from ml_task_matching_v5.policy import cv_facts, inspect_pair, job_facts, judge, task_evidence


class TaskMatchingV5Tests(WorkspaceTest):
    def payload(self):
        return dict(
            cv=dict(role="Platform Engineer", text="Tôi triển khai Kubernetes bằng Python."),
            jd=dict(
                title="Site Reliability Engineer",
                tasks_text="Triển khai Kubernetes.",
                requirements_text="Must know Kubernetes and Python",
                preferred_requirements_text="",
            ),
        )

    def test_unseen_titles_allowed_and_no_required_years_needed(self):
        result = inspect_pair(self.payload())
        self.assertEqual(result["decision"]["relevance_0_1_2"], "2")
        self.assertFalse(result["decision"]["title_used_for_decision"])

    def test_title_and_role_renaming_invariant(self):
        payload = self.payload()
        before = inspect_pair(payload)["decision"]
        for cv_role, title in (
            ("", ""),
            ("Quantum Banana Specialist", "Unknown Position 2050"),
            ("Backend Python", "Backend Python"),
            ("Bác sĩ", "Luật sư"),
        ):
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
        for text in (
            "I never deploy Kubernetes.",
            "Tôi chưa triển khai Kubernetes.",
            "If needed, deploy Kubernetes.",
            "Tôi muốn học triển khai Kubernetes.",
            "I train staff to deploy Kubernetes.",
        ):
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

    def test_subordinate_negation_does_not_drop_prior_clause_task_or_skill(self):
        text = "Flutter và Dart xây màn nhập ngoại tuyến, SQLite giữ lần ghi chưa đồng bộ."
        cv = cv_facts(text)
        self.assertIn("mobile_application", cv["functions"])
        self.assertTrue({"flutter", "dart", "sqlite"} <= set(cv["skills"]))
        for span in cv["skills"].values():
            self.assertEqual(text[span["start"]:span["end"]], span["quote"])

    def test_carrier_subject_task_patterns(self):
        self.assertIn("backend_services", task_evidence("C#, ASP.NET Core và SQL Server lưu khoảng ngày.", "cv_text", "cv")[0])
        self.assertIn("user_interface", task_evidence("React, TypeScript và CSS hiển thị sức chứa theo ca.", "cv_text", "cv")[0])
        self.assertIn("quality_testing", task_evidence("Postman thử hủy lịch và Jira lưu lỗi.", "cv_text", "cv")[0])
        self.assertIn("infrastructure_operations", task_evidence("Linux, Ansible và Docker quản lý máy giả lập.", "cv_text", "cv")[0])

    def test_explicit_clause_nonuse_contradicts_mandatory_requirement(self):
        payload = dict(
            cv=dict(
                role="Backend Java",
                text="Java, Spring Boot và PostgreSQL giữ quan hệ chia lô. Chưa chứng nhận nguồn gốc sản phẩm thật, chưa sử dụng Kafka.",
            ),
            jd=dict(
                title="Java Engineer",
                tasks_text="Xây dựng API backend.",
                requirements_text="Proficiency in Java and Spring Boot frameworks.\nExperience with databases such as MySQL and messaging systems like Kafka.",
                preferred_requirements_text="",
            ),
        )
        result = inspect_pair(payload)
        self.assertIn("kafka", result["cv_facts"]["nonuse"])
        self.assertEqual(result["decision"]["relevance_0_1_2"], "0")
        self.assertEqual(result["decision"]["reason"], "explicit_mandatory_contradiction")

    def test_parenthetical_and_one_of_requirement_trees(self):
        payload = dict(
            cv=dict(
                role="Fullstack",
                text="Tôi có 38 tháng kinh nghiệm nghề nghiệp qua hợp đồng. Tôi nhận cả phần React và API Node.js; dùng PostgreSQL cho các luồng phản hồi.",
            ),
            jd=dict(
                title="Junior Developer",
                tasks_text="- Xây dựng các thư viện, API dùng chung cho các sản phẩm\n- Viết các đoạn code chất lượng: rõ ràng, dễ dàng bảo trì, tái sử dụng",
                requirements_text=(
                    "- Tốt nghiệp Đại học chuyên ngành Công nghệ thông tin\n"
                    "- Có kinh nghiệm làm việc thực tế với một trong các Web framework phổ biến: Django, Ruby on Rails, Node.js, PHP,…\n"
                    "- Có kinh nghiệm làm việc thực tế với hệ cơ sở quản trị dữ liệu: MySQL, PostgreSQL, MongoDB\n"
                    "- Kinh nghiệm làm việc từ 1 năm trở lên"
                ),
                preferred_requirements_text="",
            ),
        )
        result = inspect_pair(payload)
        self.assertEqual(result["decision"]["relevance_0_1_2"], "2")
        self.assertTrue(result["jd_facts"]["requirement_coverage"]["complete_bounded_grammar"])
        payload["jd"]["requirements_text"] += "\n- Must know SecretFramework"
        self.assertEqual(inspect_pair(payload)["decision"]["relevance_0_1_2"], "1")

    def test_sealed_v5_runs_are_byte_identical_and_contract_valid(self):
        from ml_data.common import ROOT, file_hash, read_json, verify
        run1 = ROOT / "ml_data_runs" / "20261117_task_matching_v5_01"
        run2 = ROOT / "ml_data_runs" / "20261117_task_matching_v5_02"
        if run1.exists() and run2.exists():
            verify(run1, "task-evidence-development-v5")
            verify(run2, "task-evidence-development-v5")
            self.assertEqual(file_hash(run1 / "manifest.json"), file_hash(run2 / "manifest.json"))
            summary = read_json(run1 / "summary.json")
            self.assertEqual(summary["task_coverage"]["cv_after"], 120)
            self.assertEqual(summary["labels"], {"0": 290, "1": 4227, "2": 3, "unlabeled": 43764})
            self.assertEqual(summary["title_ablation_checked_pairs"], 48284)
            self.assertFalse(summary["ready_for_training"])

