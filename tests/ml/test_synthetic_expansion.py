"""Structural/evidence tests only; no ranking, labels or parser tuning on CVs."""
from copy import deepcopy
import json

from _support import ROOT, WorkspaceTest
from ml_data.common import csv_rows, file_hash, read_json, read_lines, verify, write_csv, write_json
from ml_data.expansion import CV_COLUMNS, assert_frozen_jd, workload_and_distribution
from ml_data.ingest import ingest
from ml_data.sampling import choose_mixed, sample_pairs
from ml_data.splitting import make_split
from ml_data.synthetic import render_batch, render_scenario


class SyntheticExpansionTests(WorkspaceTest):
    def setUp(self):
        super().setUp()
        self.assets = ROOT / "ml_data_assets/synthetic_cv_v1"
        self.design = read_json(self.assets / "design.json")

    def fixture(self):
        return dict(id="CVX_XX_01", role="Backend Python", family="personal_portfolio",
                    blocks=["TEST ONLY. Dự án thử nghiệm trong 5 tháng, không phải thời gian làm việc chính thức.",
                            "TEST ONLY. Dùng Python và pytest để kiểm tra xử lý đầu vào của một công cụ học tập.",
                            "TEST ONLY. Chưa có số tháng riêng cho từng công nghệ và không có dữ liệu người thật."],
                    skills={"Python": 1, "pytest": 1}, stack=["Python"],
                    duration=dict(scope="dự án thử nghiệm", months=5, block=0, kind="project"))

    def test_literal_evidence_offsets_and_unknown_not_zero(self):
        scenario = self.fixture()
        row, evidence = render_scenario(scenario, self.design)
        self.assertEqual(json.loads(row["experience_json"]), {"dự án thử nghiệm": 5})
        for item in [*evidence["skills"].values(), *evidence["durations"]]:
            self.assertEqual(row["cv_text"][item["start"]:item["end"]], item["quote"])
        self.assertEqual(evidence["lineage"]["experience_kind"], "project")
        scenario["duration"] = None
        row, evidence = render_scenario(scenario, self.design)
        self.assertEqual(row["experience_json"], "{}")
        self.assertEqual(evidence["durations"], [])
        self.assertEqual(evidence["lineage"]["experience_kind"], "unknown")

    def test_reject_unsupported_metadata_and_scope(self):
        for change in (lambda s: s["skills"].update({"Java": 1}),
                       lambda s: s["duration"].update(months=50),
                       lambda s: s["duration"].update(months=0),
                       lambda s: s["duration"].update(scope="python"),
                       lambda s: s["stack"].append("Docker")):
            with self.subTest(change=change):
                scenario = self.fixture()
                change(scenario)
                with self.assertRaises(ValueError):
                    render_scenario(scenario, self.design)

    def test_batch_schema_reproducibility_and_tamper_detection(self):
        first, second = self.folder / "first", self.folder / "second"
        summary = render_batch(self.assets, first)
        render_batch(self.assets, second)
        self.assertEqual(summary["cv_count"], 60)
        self.assertEqual(summary["source_groups"], 60)
        self.assertEqual(summary["template_groups"], 6)
        self.assertEqual(set(summary["roles"].values()), {12})
        self.assertEqual(file_hash(first / "manifest.json"), file_hash(second / "manifest.json"))
        verify(first, "synthetic-cvs")
        columns, rows = csv_rows(first / "cvs.csv")
        self.assertEqual(set(columns), set(CV_COLUMNS.values()))
        self.assertTrue(all(r["is_synthetic"] == "true" and r["exposure"] == "prospective" for r in rows))
        self.assertEqual(sum(r["experience_json"] == "{}" for r in rows), 10)
        evidence = {e["cv_id"]: e for e in read_json(first / "evidence.json")}
        for row in rows:
            item = evidence[row["cv_id"]]
            self.assertEqual(json.loads(row["lineage_json"]), item["lineage"])
            for quote in [*item["skills"].values(), *item["durations"]]:
                self.assertEqual(row["cv_text"][quote["start"]:quote["end"]], quote["quote"])
        with self.assertRaises(FileExistsError):
            render_batch(self.assets, first)
        (first / "cvs.csv").write_text("tampered", encoding="utf-8")
        with self.assertRaises(ValueError):
            verify(first, "synthetic-cvs")

    def test_frozen_jd_checks_full_quality_lineage_and_exposure(self):
        old = [dict(kind="jd", record_id="TEST_JD", text_original="TEST ONLY", group_id="group",
                    development_only=True, decision="quarantine", lineage={"raw": 3}, decision_reasons=["bad section"])]
        self.assertEqual(assert_frozen_jd(old, deepcopy(old))["development_records"], 1)
        for field, value in (("development_only", False), ("lineage", {}), ("decision", "keep"),
                             ("decision_reasons", []), ("text_original", "changed"), ("group_id", "new")):
            changed = deepcopy(old)
            changed[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                assert_frozen_jd(old, changed)
        with self.assertRaises(ValueError):
            assert_frozen_jd(old, [])

    def test_preview_workload_matches_sampler_preserves_whole_families(self):
        batch, dataset, split = (self.folder / name for name in ("batch", "dataset", "split"))
        render_batch(self.assets, batch)
        # TEST ONLY JD content, not a target used for scenario authoring.
        jobs = [dict(id=f"TEST_JD_{i}", text="TEST ONLY fictional description " + " ".join(f"unique{i}word{k}" for k in range(30)))
                for i in range(7)]
        write_csv(self.folder / "jobs.csv", jobs, ("id", "text"))
        config = dict(schema_version=1, dataset_version="TEST_ONLY", sources=[
            dict(path="batch/cvs.csv", kind="cv", namespace="TEST_ONLY_CV", version="test-v1", columns=CV_COLUMNS),
            dict(path="jobs.csv", kind="jd", namespace="TEST_ONLY_JD", version="test-v1",
                 columns=dict(external_id="id", text="text"), defaults=dict(exposure="prospective", text_scope="professional"))])
        write_json(self.folder / "config.json", config)
        ingest(self.folder / "config.json", dataset)
        make_split(dataset, split)
        records, assignments = read_lines(dataset / "records.jsonl"), read_lines(split / "assignments.jsonl")
        report = workload_and_distribution(records, assignments, 20261113)
        by_id = {r["record_id"]: r for r in records}
        families = {}
        for a in assignments:
            if a["kind"] == "cv":
                families.setdefault(by_id[a["record_id"]]["template_group"], set()).add(a["partition"])
        self.assertEqual(len(families), 6)
        self.assertTrue(all(len(partitions) == 1 for partitions in families.values()))
        self.assertEqual(sorted(d["cv_count"] for d in report["distributions"].values()), [10, 20, 30])
        self.assertTrue(all(d["missing_experience_kinds"] for d in report["distributions"].values()))
        sampled = sample_pairs(dataset, split, self.folder / "pairs")
        self.assertEqual(sampled["pairs"], report["workload"]["pairs_by_partition"]["train"])
        self.assertEqual(sampled["by_strategy"], report["workload"]["train_by_strategy"])
        self.assertEqual(len(sampled["shortages"]), report["workload"]["hard_shortage_cv_categories"])
        self.assertEqual(report["workload"]["pair_files_created"], 0)
        self.assertEqual(report["catalogue"]["missing_metadata"], dict(skills=7, stack=7, experience=7))
        for part in ("validation", "test"):
            self.assertEqual(report["workload"]["pairs_by_partition"][part], report["distributions"][part]["cv_count"] * 7)

    def test_mixed_candidate_plan_deterministic_nonoverlapping_and_unlabeled(self):
        cv = dict(record_id="CV_TEST", role="backend", skills=["python"], stack=["django"], experience={"backend": 12})
        jobs = [dict(record_id=f"JD_TEST_{i}", role="data" if i < 7 else "backend", skills=["python"],
                     stack=["fastapi"], experience={"backend": 36}) for i in range(20)]
        first, missing = choose_mixed(cv, jobs, "train", 20261113, 3, 2)
        second, _ = choose_mixed(cv, list(reversed(jobs)), "train", 20261113, 3, 2)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 9)
        self.assertEqual(missing, [])
        self.assertEqual(set(first.values()), {"uniform_random_without_replacement", "shared_skill_different_role",
                                              "shared_skill_different_stack", "scoped_experience_requirement_gap"})
