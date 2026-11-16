"""Observed title shapes and conservative expansion of the actual canonical schema."""
from copy import deepcopy

from _support import WorkspaceTest
from ml_data.catalogue import audit_evidence
from ml_data.extraction import extract_jd_row
from ml_data.label_rules import label_pair_row
from ml_data.refinement import cv_plan, missing_reasons, refine_receipt


class RefinementTests(WorkspaceTest):
    def raw(self, title, requirements="", tasks=""):
        return dict(job_id="fixture", title_for_matching=title, requirements_text=requirements,
                    tasks_text=tasks, preferred_requirements_text="", match_text=title + "\n" + requirements)

    def refined(self, row):
        return refine_receipt(row, extract_jd_row(row))

    def test_observed_titles_preserve_occupation_over_shared_keywords(self):
        cases = {
            "Nhân Viên Lập Trình CNC (Gỗ)": "CNC/CAM Manufacturing",
            "Giáo Viên 3D Unity Game Part Time": "Education/Training",
            "Cloud Business Development Manager": "Sales/Business Development",
            "Business Analyst (SQL, ERP)": "Business Analyst",
            "Project Manager (ERP)": "Project Management",
            "Senior Fullstack TypeScript Developer (ReactJS/API/LLM)": "Fullstack",
            "Software Engineer (.NET WPF) English speaking": "Desktop Application",
            "Database Developer (Mid Level)": "Database/SQL",
            "Kỹ Sư Lập Trình Nhúng": "Embedded Engineer",
            "Backend Developer (NodeJS, Typescript/NestJS)": "Backend Node.js",
            "Node JS Developer": "Backend Node.js",
            "Unity Developer (C#, Games, English)": "Game Developer",
        }
        for title, role in cases.items():
            with self.subTest(title=title):
                self.assertEqual(self.refined(self.raw(title))["role"], role)

    def test_multiple_languages_remain_ambiguous_and_generic_is_explicit(self):
        result = self.refined(self.raw("Backend Developer (Java, NodeJS)"))
        self.assertEqual(result["role"], "")
        self.assertIn("Backend Java", result["role_candidates"])
        self.assertIn("Backend Node.js", result["role_candidates"])
        generic = self.refined(self.raw("Backend Developer"))
        self.assertEqual(generic["role"], "Backend (unspecified stack)")
        self.assertEqual(generic["role_precision"], "generic")
        self.assertEqual(self.refined(self.raw("Team Leader"))["role"], "")

    def test_technology_without_developer_title_does_not_imply_backend(self):
        result = self.refined(self.raw("Accountant", "Dùng Node JS để xuất báo cáo"))
        self.assertEqual(result["role"], "")
        self.assertIn("node.js", result["skills"])

    def test_optional_extra_skills_are_not_core_requirements(self):
        row = self.raw("Data Engineer", "Có kinh nghiệm ETL và Airflow.\nKhông yêu cầu Spark.\nƯu tiên dbt.")
        row["preferred_requirements_text"] = "Biết PyTorch là lợi thế."
        result = self.refined(row)
        self.assertIn("airflow", result["skills"])
        self.assertTrue({"spark", "dbt", "pytorch"} <= set(result["preferred_skills"]))
        self.assertFalse({"spark", "dbt", "pytorch"} & set(result["skills"]))

    def test_literal_evidence_and_duration_are_preserved_without_input_mutation(self):
        row = self.raw("Data Engineer", "Ít nhất 3 năm kinh nghiệm phát triển phần mềm.\nDùng Airflow và Spark.")
        previous = extract_jd_row(row)
        before = deepcopy(previous)
        result = refine_receipt(row, previous)
        self.assertEqual(previous, before)
        self.assertEqual(result["experience"], previous["experience"])
        self.assertNotIn("airflow", result["experience"])
        canonical = dict(row, extracted_role=result["role"], extracted_skills=";".join(result["skills"]),
                         extracted_stack=";".join(result["stack"]), extracted_experience_json="{}")
        import json
        canonical["extracted_experience_json"] = json.dumps(result["experience"])
        self.assertGreater(audit_evidence([canonical], [result])["literal_spans_verified"], 0)

    def test_unknown_months_remain_empty_and_reason_is_not_zero(self):
        row = self.raw("Backend Developer", "Sử dụng NestJS; thời gian kinh nghiệm không được nêu.")
        result = self.refined(row)
        self.assertEqual(result["experience"], {})
        self.assertEqual(missing_reasons(row, result)["experience"], "no_numeric_duration_in_requirements")
        numeric = self.raw("Backend Developer", "3+ years.")
        self.assertEqual(missing_reasons(numeric, self.refined(numeric))["experience"],
                         "numeric_duration_without_supported_scope_or_minimum")

    def test_old_proxy_cannot_silently_label_expanded_taxonomy(self):
        cv = dict(role="backend java", skills=["java"], stack=[], experience={})
        jd = dict(role="fullstack", skills=["java"], stack=[], experience={},
                  label_policy_status="requires_expanded_taxonomy_policy")
        result = label_pair_row(dict(cv_text="CV", jd_text="JD"), cv, jd)
        self.assertEqual(result["label_status"], "insufficient_evidence")
        self.assertEqual(result["relevance_0_1_2"], "")

    def test_cv_design_is_only_a_plan_and_retains_uncovered_roles(self):
        records = [dict(role="backend java", group_id="G1"), dict(role="backend node.js", group_id="G2")]
        plan = cv_plan(records)
        self.assertEqual(plan["proposed_cv_count"], 20)
        self.assertEqual(plan["validation_pairs"], 8)
        self.assertEqual(plan["uncovered_roles"], {"backend node.js": 1})
        self.assertEqual(plan["status"], "design_only_no_cvs_generated")
