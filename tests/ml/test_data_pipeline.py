"""TEST ONLY synthetic documents. No reviewer responses or real relevance labels."""
import csv
import random

from _support import ROOT, WorkspaceTest
from ml_data.common import (digest, file_hash, read_json, read_lines, verify, write_json)
from ml_data.grouping import near_pairs, shingles
from ml_data.ingest import ingest, record
from ml_data.sampling import candidate_reasons, sample_pairs
from ml_data.splitting import audit_assignments, audit_split, make_split


class DataPipelineTests(WorkspaceTest):
    def setUp(self):
        super().setUp()
        self.cvs = [self.document("cv", i) for i in range(9)]
        self.jobs = [self.document("jd", i) for i in range(30)]
        self.config = self.folder / "config.json"
        self.config_value = dict(schema_version=1, dataset_version="TEST_ONLY_v1", near_threshold=0.85, sources=[
            dict(path=kind + ".csv", kind=kind, namespace="TEST_ONLY_" + kind, version="TEST_ONLY_v1",
                 columns={key: key for key in self.cvs[0]}, defaults=dict(text_scope="professional"))
            for kind in ("cv", "jd")])
        write_json(self.config, self.config_value)
        self.dataset = self.folder / "dataset"

    def document(self, kind, number):
        # Distinct vocabulary avoids unintended near duplicates in split fixtures.
        return dict(external_id=f"TEST_{kind}_{number}", text="TEST ONLY fictional document " +
                    " ".join(f"{kind}{number}skill{j}" for j in range(25)),
                    source_group=f"TEST_{kind}_source_{number}", template_group=f"TEST_{kind}_template_{number}",
                    role="backend" if kind == "cv" or number % 3 else "data", skills="python;sql",
                    stack="django" if kind == "cv" or number % 2 else "fastapi",
                    experience='{"backend": 12}' if kind == "cv" else '{"backend": 36}',
                    is_synthetic="true", exposure="prospective")

    def build(self, name=None):
        for kind, rows in (("cv", self.cvs), ("jd", self.jobs)):
            with (self.folder / (kind + ".csv")).open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(self.cvs[0]))
                writer.writeheader()
                writer.writerows(rows)
        output = self.folder / name if name else self.dataset
        ingest(self.config, output)
        return output

    def test_raw_preservation_unknowns_stable_ids_and_reordering(self):
        self.cvs[0]["experience"] = ""
        first = self.build()
        before = file_hash(self.folder / "cv.csv")
        self.assertEqual(before, file_hash(first / "raw/000.csv"))
        rows = read_lines(first / "records.jsonl")
        cv = next(r for r in rows if r["external_id"] == "TEST_cv_0")
        self.assertEqual(cv["experience"], {})
        self.assertIn("experience", cv["missing_fields"])
        self.assertEqual(cv["occurrences"][0]["raw_row"]["text"], self.cvs[0]["text"])
        self.cvs.reverse()
        self.jobs.reverse()
        second = self.build("reordered")
        self.assertEqual([r["record_id"] for r in rows], [r["record_id"] for r in read_lines(second / "records.jsonl")])
        self.assertEqual(read_json(first / "groups.json"), read_json(second / "groups.json"))
        self.assertEqual(read_json(first / "sources.json")[0]["missing_source_metadata"], ["source_url", "collected_at", "usage_terms"])

    def test_exact_duplicate_excluded_but_original_retained(self):
        self.jobs[1]["text"] = self.jobs[0]["text"].upper().replace(" ", "  ")
        self.build()
        rows = read_lines(self.dataset / "records.jsonl")
        duplicates = [r for r in rows if r["external_id"] in {"TEST_jd_0", "TEST_jd_1"}]
        self.assertEqual({r["decision"] for r in duplicates}, {"keep", "exclude_exact_duplicate"})
        self.assertEqual(len({r["group_id"] for r in duplicates}), 1)
        self.assertTrue(all(r["occurrences"] and r["text_original"] for r in duplicates))

    def test_duplicate_source_occurrences_retained_and_entity_revisions_grouped(self):
        self.cvs.append(self.cvs[0].copy())
        changed = self.cvs[0].copy()
        changed["text"] += " changed version"
        self.cvs.append(changed)
        self.build()
        rows = [r for r in read_lines(self.dataset / "records.jsonl") if r["external_id"] == "TEST_cv_0"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(sorted(len(r["occurrences"]) for r in rows), [1, 2])
        self.assertEqual(len({r["group_id"] for r in rows}), 1)

    def test_missing_metadata_quarantined_not_filled_with_zero(self):
        self.cvs[0]["source_group"] = ""
        self.cvs[1]["template_group"] = ""
        self.cvs[2]["is_synthetic"] = ""
        self.build()
        rows = {r["external_id"]: r for r in read_lines(self.dataset / "records.jsonl")}
        self.assertTrue(all(rows[f"TEST_cv_{i}"]["decision"] == "quarantine" for i in range(3)))
        self.assertIsNone(rows["TEST_cv_2"]["is_synthetic"])

    def test_unreviewed_raw_text_quarantined_and_invalid_scopes_rejected(self):
        spec = dict(kind="cv", namespace="TEST", columns={k: k for k in self.cvs[0]})
        row = record(self.cvs[0], spec)
        self.assertEqual(row["decision"], "quarantine")
        for value in ('{"python": true}', '{"python": -1}', '{"python": null}', '{"python": 1.5}'):
            self.cvs[0]["experience"] = value
            with self.assertRaises(ValueError):
                record(self.cvs[0], spec)

    def test_near_prefix_search_matches_bruteforce(self):
        rng = random.Random(14)
        rows = [dict(record_id=str(i), text_normalized=" ".join(rng.choices(list("abcdefghij"), k=20))) for i in range(25)]
        rows += [dict(record_id="near", text_normalized=rows[0]["text_normalized"] + " end")]
        for threshold in (0.15, 0.5, 0.85, 1):
            expected = set()
            for i, a in enumerate(rows):
                sa = shingles(a["text_normalized"])
                for b in rows[i+1:]:
                    sb = shingles(b["text_normalized"])
                    if len(sa & sb) / len(sa | sb) >= threshold:
                        expected.add(tuple(sorted((a["record_id"], b["record_id"]))))
            actual = {tuple(sorted((a, b))) for a, b, _ in near_pairs(rows, threshold)}
            self.assertEqual(actual, expected)

    def test_source_template_near_transitive_families_stay_together(self):
        self.cvs[1]["source_group"] = self.cvs[0]["source_group"]
        self.cvs[2]["template_group"] = self.cvs[1]["template_group"]
        self.cvs[3]["text"] = self.cvs[2]["text"] + " tiny change"
        self.build()
        split = self.folder / "split"
        make_split(self.dataset, split, "new-both")
        rows = {r["record_id"]: r for r in read_lines(self.dataset / "records.jsonl")}
        assignments = read_lines(split / "assignments.jsonl")
        family = [a for a in assignments if rows[a["record_id"]]["external_id"] in {f"TEST_cv_{i}" for i in range(4)}]
        self.assertEqual(len({r["group_id"] for r in family}), 1)
        self.assertEqual(len({r["partition"] for r in family}), 1)
        self.assertTrue(audit_split(self.dataset, split)["leakage_check_passed"])

    def test_pilot_and_related_family_never_enter_final_partitions(self):
        from ml_data.common import csv_rows
        _, pilot = csv_rows(ROOT / "jobapply_pilot_v1/cvs_synthetic.csv")
        self.cvs[0]["text"] = pilot[0]["cv_text"]  # Changed ID still detected by content.
        self.cvs[1]["source_group"] = self.cvs[0]["source_group"]
        self.jobs[0]["external_id"] = "job_" + "unused"
        _, pilot_jobs = csv_rows(ROOT / "jobapply_pilot_v1/jobs_pilot.csv")
        self.jobs[0]["external_id"] = pilot_jobs[0]["job_id"]  # Changed content, retained pilot ID.
        self.build()
        for mode in ("known-jd", "new-both"):
            target = self.folder / mode
            report = make_split(self.dataset, target, mode)
            self.assertEqual(report["counts"]["cv"]["development"], 2)
            self.assertEqual(report["counts"]["jd"]["development"], 1)
            self.assertTrue(audit_split(self.dataset, target)["leakage_check_passed"])

    def test_seed_determinism_and_protocols(self):
        self.build()
        for mode in ("known-jd", "new-both"):
            a, b = self.folder / (mode + "a"), self.folder / (mode + "b")
            make_split(self.dataset, a, mode, 101)
            make_split(self.dataset, b, mode, 101)
            self.assertEqual((a / "assignments.jsonl").read_bytes(), (b / "assignments.jsonl").read_bytes())
            report = audit_split(self.dataset, a)
            self.assertTrue(report["partition_ready"])
            self.assertFalse(report["final_test_ready"])
            if mode == "known-jd":
                self.assertEqual(report["counts"]["jd"], {"shared": 30})
            else:
                self.assertEqual(set(report["counts"]["jd"]), {"train", "validation", "test"})
        other = self.folder / "otherseed"
        make_split(self.dataset, other, "new-both", 102)
        self.assertNotEqual((other / "assignments.jsonl").read_bytes(), (self.folder / "new-botha/assignments.jsonl").read_bytes())

    def test_leakage_audit_rejects_broken_family_and_pilot(self):
        self.cvs[1]["source_group"] = self.cvs[0]["source_group"]
        self.cvs[2]["exposure"] = "development"
        self.build()
        split = self.folder / "split"
        make_split(self.dataset, split, "known-jd")
        rows = read_lines(self.dataset / "records.jsonl")
        groups = read_json(self.dataset / "groups.json")
        assignments = read_lines(split / "assignments.jsonl")
        by_ext = {r["external_id"]: r["record_id"] for r in rows}
        for a in assignments:
            if a["record_id"] == by_ext["TEST_cv_0"]:
                a["partition"] = "train"
            elif a["record_id"] in {by_ext["TEST_cv_1"], by_ext["TEST_cv_2"]}:
                a["partition"] = "test"
        result = audit_assignments(rows, groups, assignments, "known-jd")
        self.assertFalse(result["leakage_check_passed"])
        self.assertTrue(any("crosses" in e for e in result["errors"]))
        self.assertTrue(any("leaked" in e for e in result["errors"]))

    def test_artifact_tampering_missing_source_and_overwrite_fail(self):
        self.build()
        verify(self.dataset, "dataset")
        with self.assertRaises(FileExistsError):
            ingest(self.config, self.dataset)
        with self.assertRaises(ValueError):
            make_split(self.dataset, self.dataset / "nested", "known-jd")
        with (self.dataset / "records.jsonl").open("a", encoding="utf-8") as stream:
            stream.write("\n")
        with self.assertRaises(ValueError):
            make_split(self.dataset, self.folder / "bad", "known-jd")
        (self.folder / "cv.csv").unlink()
        with self.assertRaises(FileNotFoundError):
            ingest(self.config, self.folder / "missing")
        self.assertFalse((self.folder / "missing").exists())

    def test_only_development_cannot_become_test_or_sample(self):
        for row in self.cvs + self.jobs:
            row["exposure"] = "development"
        self.build()
        split = self.folder / "split"
        report = make_split(self.dataset, split, "new-both")
        self.assertFalse(report["partition_ready"])
        self.assertEqual(report["counts"], {"cv": {"development": 9}, "jd": {"development": 30}})
        with self.assertRaises(ValueError):
            sample_pairs(self.dataset, split, self.folder / "badpairs")

    def test_hard_reasons_are_candidates_not_labels(self):
        cv = dict(skills=["python"], role="backend", stack=["django"], experience={"python": 12})
        other = dict(skills=["python"], role="data", stack=["pandas"], experience={"python": 36})
        self.assertEqual(candidate_reasons(cv, other), ["shared_skill_different_role", "scoped_experience_requirement_gap"])
        other.update(role="backend", experience={}, stack=["fastapi"])
        self.assertEqual(candidate_reasons(cv, other), ["shared_skill_different_stack"])
        other["skills"] = []
        self.assertEqual(candidate_reasons(cv, other), [])

    def test_sampling_after_split_reproducible_unlabeled_and_train_only(self):
        self.build()
        split = self.folder / "split"
        make_split(self.dataset, split, "known-jd")
        a, b = self.folder / "pairsA", self.folder / "pairsB"
        report = sample_pairs(self.dataset, split, a, seed=10)
        sample_pairs(self.dataset, split, b, seed=10)
        self.assertEqual((a / "pairs.csv").read_bytes(), (b / "pairs.csv").read_bytes())
        from ml_data.common import csv_rows
        _, pairs = csv_rows(a / "pairs.csv")
        self.assertEqual(len({r["pair_id"] for r in pairs}), len(pairs))
        self.assertTrue(all(r["label_status"] == "unlabeled" and r["relevance_0_1_2"] == "" and r["annotation_origin"] == "" for r in pairs))
        self.assertTrue(all(digest(r["cv_text"]) == r["cv_version"] and digest(r["jd_text"]) == r["jd_version"] for r in pairs))
        self.assertIn("uniform_random_without_replacement", report["by_strategy"])
        self.assertEqual({r["partition"] for r in pairs}, {"train"})
        with self.assertRaises(ValueError):
            sample_pairs(self.dataset, split, self.folder / "badtest", partition="test")

    def test_census_is_complete_budget_not_silently_truncated(self):
        self.build()
        split = self.folder / "split"
        make_split(self.dataset, split, "new-both")
        with self.assertRaises(ValueError):
            sample_pairs(self.dataset, split, self.folder / "smallbudget", "test", "census", max_pairs=1)
        out = self.folder / "census"
        report = sample_pairs(self.dataset, split, out, "test", "census")
        self.assertEqual(report["pairs"], report["cv_count"] * report["jd_count"])
        self.assertEqual(report["label_counts"], {"unlabeled": report["pairs"]})

    def test_missing_sampling_metadata_reports_shortage_without_invention(self):
        for row in self.cvs + self.jobs:
            row.update(skills="", stack="", experience="")
        self.build()
        split = self.folder / "split"
        make_split(self.dataset, split, "known-jd")
        report = sample_pairs(self.dataset, split, self.folder / "pairs")
        self.assertEqual(set(report["by_strategy"]), {"uniform_random_without_replacement"})
        self.assertTrue(report["shortages"])


if __name__ == "__main__":
    import unittest
    unittest.main()
