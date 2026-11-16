"""Historical lineage and extraction regressions; no reviewer workflow."""
from copy import deepcopy
import json

from _support import WorkspaceTest
from ml_data.jd_integrity import assert_frozen_jd_identity_and_exposure
from ml_data.common import read_json, read_lines, write_csv, write_json
from ml_data.expansion import CV_COLUMNS, workload_and_distribution
from ml_data.extraction import evaluate_pilot_extraction, extract_jd_row
from ml_data.ingest import ingest
from ml_data.sampling import sample_pairs
from ml_data.splitting import audit_split, make_split
from ml_data.synthetic import FIELDS


class BenchmarkPrepTests(WorkspaceTest):
    def test_jd_extractor_literal_offsets_boundaries_and_unknown_preservation(self):
        row = dict(
            job_id="TEST_JD_01",
            title_for_matching="Senior Backend Python Developer (Django, FastAPI)",
            tasks_text="Xây dựng REST API với FastAPI, kết nối PostgreSQL và triển khai bằng Docker Compose.",
            requirements_text="- Tối thiểu 3 năm kinh nghiệm phát triển backend với Python.\n- Thành thạo JavaScript và React Native là không bắt buộc.",
            preferred_requirements_text="Ưu tiên biết Kubernetes và GitHub Actions.",
            unclassified_professional_text="",
            match_text="Senior Backend Python Developer",
        )
        receipt = extract_jd_row(row)
        self.assertEqual(receipt["role"], "Backend Python")
        self.assertIn("python", receipt["skills"])
        self.assertIn("fastapi", receipt["stack"])
        self.assertIn("django", receipt["stack"])
        self.assertIn("postgresql", receipt["stack"])
        self.assertIn("docker compose", receipt["stack"])
        self.assertNotIn("docker", receipt["stack"])
        self.assertNotIn("javascript", receipt["skills"])
        self.assertIn("javascript", receipt["preferred_skills"])
        self.assertNotIn("java", receipt["skills"])
        self.assertNotIn("react native", receipt["stack"])
        self.assertNotIn("react", receipt["stack"])
        self.assertIn("kubernetes", receipt["preferred_skills"])
        self.assertIn("github actions", receipt["preferred_skills"])
        self.assertNotIn("git", receipt["skills"])
        self.assertEqual(receipt["experience"].get("backend python"), 36)

        for item in [
            *receipt["role_evidence"],
            *receipt["skill_evidence"].values(),
            *receipt["stack_evidence"].values(),
            *receipt["preferred_skill_evidence"].values(),
            *receipt["experience_evidence"],
        ]:
            self.assertEqual(row[item["field"]][item["start"]:item["end"]], item["quote"])

        # Internship duration and vague experience must stay unknown ({})
        intern_row = dict(
            job_id="TEST_JD_INTERN",
            title_for_matching="DevOps Engineer Intern",
            tasks_text="Hỗ trợ vận hành hệ thống Linux.",
            requirements_text="- At least 4 working days per week in 3-6 months of internship.\n- A few years of general interest in Linux.",
            preferred_requirements_text="",
            unclassified_professional_text="",
            match_text="DevOps Engineer Intern",
        )
        intern_receipt = extract_jd_row(intern_row)
        self.assertEqual(intern_receipt["experience"], {})
        self.assertIn("experience", intern_receipt["unknown_fields"])

    def test_pilot_extraction_evaluation_metrics(self):
        report = evaluate_pilot_extraction()
        self.assertEqual(report["pilot_jd_count"], 50)
        self.assertGreaterEqual(report["role_accuracy"], 0.94)
        self.assertIn("comparison_note", report["experience_detection"])
        self.assertIn("max_threshold_value_match_count", report["experience_detection"])

    def test_reassigned_templates_collapse_when_ancestry_is_preserved(self):
        # TEST ONLY: six short documents, two original families interleaved
        # across three renamed families. Preserving ancestry connects all six.
        batch_dir = self.folder / "cv_v2"
        batch_dir.mkdir()
        cvs = [dict(cv_id=f"TEST_CV_{i}",
                    cv_text="TEST ONLY " + " ".join(f"cv{i}word{k}" for k in range(30)),
                    source_group=f"test-source-{i}", template_group=f"TEST_RENAMED_{i // 2}",
                    is_synthetic="true", role="Backend Python", skills="python", stack="django",
                    experience_json="{}", exposure="prospective", text_scope="professional",
                    lineage_json=json.dumps(dict(parent_ids=[f"TEST_PARENT_{i}"], template_family=f"TEST_RENAMED_{i // 2}",
                        template_ancestors=[f"TEST_ORIGINAL_{i % 2}"],
                        variant_history=[dict(version=2, action="TEST ONLY reassignment")], experience_kind="unknown")))
               for i in range(6)]
        write_csv(batch_dir / "cvs.csv", cvs, FIELDS)

        # Build a synthetic JD fixture with 15 JDs (3 per benchmark role) to test split & eval catalogue
        roles = ("Backend Python", "Backend Java", "Frontend", "DevOps/Cloud", "QA/Testing")
        jobs = []
        for idx in range(15):
            role = roles[idx % 5]
            jobs.append(dict(
                id=f"TEST_JD_{idx:02d}",
                text="TEST ONLY fictional description " + " ".join(f"jd{idx}token{k}" for k in range(30)),
                source_group=f"jd_group_{idx:02d}",
                role=role,
                skills="python;sql;java;frontend;devops;kiểm thử",
                stack="django;spring boot;react;terraform;selenium",
                experience='{"backend python": 36, "backend java": 48, "frontend": 36, "devops": 48, "kiểm thử phần mềm": 36}',
            ))
        write_csv(self.folder / "jobs.csv", jobs, ("id", "text", "source_group", "role", "skills", "stack", "experience"))
        config = dict(
            schema_version=1,
            dataset_version="TEST_V2_COMBINED",
            sources=[
                dict(path="cv_v2/cvs.csv", kind="cv", namespace="TEST_CV_V2", version="v2", columns=CV_COLUMNS),
                dict(
                    path="jobs.csv",
                    kind="jd",
                    namespace="TEST_JD_V2",
                    version="v2",
                    columns=dict(external_id="id", text="text", source_group="source_group", role="role", skills="skills", stack="stack", experience="experience"),
                    defaults=dict(exposure="prospective", text_scope="professional"),
                ),
            ],
        )
        write_json(self.folder / "config.json", config)
        dataset = self.folder / "dataset"
        split = self.folder / "split"
        ingest(self.folder / "config.json", dataset)
        make_split(dataset, split, mode="known-jd", seed=20261113, eval_jd_per_role=2)
        audit = audit_split(dataset, split)
        self.assertTrue(audit["leakage_check_passed"])

        records = read_lines(dataset / "records.jsonl")
        assignments = read_lines(split / "assignments.jsonl")
        plan = workload_and_distribution(records, assignments, 20261113)
        self.assertFalse(audit["partition_ready"])
        self.assertEqual(plan["distributions"]["train"]["cv_count"], 6)
        self.assertEqual(plan["distributions"]["train"]["group_count"], 1)
        self.assertEqual(plan["distributions"]["validation"]["cv_count"], 0)
        self.assertEqual(plan["distributions"]["test"]["cv_count"], 0)
        self.assertEqual(read_json(split / "eval_catalogue.json")["total_eval_jds"], 10)
        with self.assertRaisesRegex(ValueError, "independent"):
            sample_pairs(dataset, split, self.folder / "must_not_sample", partition="train")
        self.assertFalse((self.folder / "must_not_sample").exists())

    def test_frozen_jd_identity_and_exposure_check(self):
        old = [dict(
            kind="jd", record_id="JD_1", entity_id="E_1", external_id="job_1", namespace="ns",
            text_original="orig", text_normalized="norm", text_sha256="h1", normalized_text_sha256="h2",
            normalized_sha256="h3", source_group="sg", template_group="", is_synthetic=False,
            exposure="development", text_scope="professional", upstream_text_sha256="uh",
            decision="keep", decision_reasons=["retained"], related_source_keys=["u1"],
            lineage={"raw": 1}, group_id="G_1", development_only=True,
            role="", skills=[], stack=[], experience={},
        )]
        enriched = deepcopy(old)
        enriched[0].update(role="backend python", skills=["python"], stack=["django"], experience={"backend python": 24})
        res = assert_frozen_jd_identity_and_exposure(old, enriched)
        self.assertTrue(res["identity_text_gate_exposure_identical"])
        for bad_field, bad_val in (("decision", "quarantine"), ("development_only", False), ("text_original", "tampered"), ("group_id", "G_2")):
            broken = deepcopy(enriched)
            broken[0][bad_field] = bad_val
            with self.subTest(field=bad_field), self.assertRaises(ValueError):
                assert_frozen_jd_identity_and_exposure(old, broken)

