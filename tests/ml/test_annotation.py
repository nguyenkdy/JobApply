"""All filled labels/identities below are fabricated TEST ONLY data, never reviewer submissions."""
import csv
import shutil

from _support import PILOT, WorkspaceTest
from annotation import (FIELDS, RESPONSE, agreement, compare_reviews, load_batch, prepare,
                        validate_adjudication, validate_reviews)
from baseline_common import read_csv, sha256, write_json


class AnnotationTests(WorkspaceTest):
    def setUp(self):
        super().setUp()
        self.run = self.folder / "fixture_run_NOT_A_TRAINED_MODEL"
        self.run.mkdir()
        for name in ("jobs_pilot.csv", "cvs_synthetic.csv", "jobapply_experience_v2/jd_experience.csv", "jobapply_experience_v2/cv_experience.csv"):
            target = self.run / "inputs" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(PILOT / name, target)
        write_json(self.run / "manifest.json", dict(status="complete", fixture="TEST ONLY, no training/labels",
                   artifacts={p.relative_to(self.run).as_posix(): dict(sha256=sha256(p)) for p in self.run.rglob("*") if p.is_file()}))
        self.batch = self.folder / "batch"
        prepare(self.run, self.batch)
        self.a = read_csv(self.batch / "reviewer_A/review.csv")
        self.b = read_csv(self.batch / "reviewer_B/review.csv")

    def save(self, rows, name):
        path = self.folder / name
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        return path

    def mark(self, row, grade="1", state="completed", origin="human_independent"):
        row.update(annotator_id="TEST_FAKE_NOT_HUMAN_" + row["reviewer_slot"], annotation_origin=origin,
                   label_status=state, relevance_0_1_2=grade, cv_evidence=row["cv_text"].splitlines()[0],
                   jd_evidence=row["jd_text"].splitlines()[0], rationale="TEST ONLY fabricated rationale for validator coverage",
                   reviewed_at="2026-11-12T15:00:00+07:00")

    def paired(self, count):
        by_b = {r["pair_id"]: r for r in self.b}
        return [(a, by_b[a["pair_id"]]) for a in self.a[:count]]

    def test_prepare_is_reproducible_and_blind_with_blank_answers(self):
        second = self.folder / "repeat"
        result = prepare(self.run, second)
        self.assertEqual(result["pairs"], 24)
        for slot in ("A", "B"):
            self.assertEqual((self.batch / f"reviewer_{slot}/review.csv").read_bytes(), (second / f"reviewer_{slot}/review.csv").read_bytes())
        self.assertNotEqual([r["pair_id"] for r in self.a], [r["pair_id"] for r in self.b])
        self.assertEqual({r["pair_id"] for r in self.a}, {r["pair_id"] for r in self.b})
        self.assertEqual(list(self.a[0]), list(FIELDS))
        self.assertTrue(all(not r[k] for r in self.a + self.b for k in RESPONSE))
        forbidden = {"cv_id", "job_id", "stratum", "selection_reason", "cosine", "bm25_score", "rank_bm25", "ai_rationale"}
        self.assertFalse(forbidden & set(self.a[0]))
        with self.assertRaises(FileExistsError):
            prepare(self.run, self.batch)

    def test_unreviewed_is_valid_but_not_zero_or_eligible(self):
        _, report = validate_reviews(self.batch, self.save(self.a, "A.csv"), "A")
        self.assertEqual(report["counts"]["unreviewed"], 24)
        self.assertEqual(report["eligible_completed"], 0)
        out = self.folder / "comparison"
        report = compare_reviews(self.batch, self.save(self.a, "A.csv"), self.save(self.b, "B.csv"), out)
        self.assertIsNone(report["agreement"]["exact_agreement"])
        self.assertIsNone(report["agreement"]["weighted_cohen_kappa"])
        self.assertEqual(report["queue_counts"], {"awaiting_reviews": 24})
        self.assertEqual(validate_adjudication(out, out / "adjudication.csv")["statuses"], {"pending": 24})

    def test_reject_schema_duplicate_unknown_missing_and_changed_version(self):
        variants = []
        duplicate = [r.copy() for r in self.a]; duplicate[-1] = duplicate[0].copy(); variants.append(duplicate)
        unknown = [r.copy() for r in self.a]; unknown[0]["pair_id"] = "alien"; variants.append(unknown)
        changed = [r.copy() for r in self.a]; changed[0]["cv_version"] = "bad"; variants.append(changed)
        changed_text = [r.copy() for r in self.a]; changed_text[0]["cv_text"] += "changed"; variants.append(changed_text)
        variants.append(self.a[:-1])
        for i, rows in enumerate(variants):
            with self.subTest(case=i), self.assertRaises(ValueError):
                validate_reviews(self.batch, self.save(rows, f"invalid_{i}.csv"), "A")
        path = self.save(self.a, "header.csv")
        path.write_text(path.read_text().replace("cv_evidence", "unexpected_evidence", 1))
        with self.assertRaises(ValueError):
            validate_reviews(self.batch, path, "A")

    def test_label_status_evidence_and_origin_validation(self):
        for key, value in (("relevance_0_1_2", ""), ("relevance_0_1_2", "3"), ("cv_evidence", ""),
                           ("jd_evidence", "invented quote"), ("rationale", ""), ("reviewed_at", "2026-11-12"),
                           ("annotation_origin", "human_adjudicated"), ("annotator_id", "")):
            rows = [r.copy() for r in self.a]; self.mark(rows[0]); rows[0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_reviews(self.batch, self.save(rows, "bad.csv"), "A")
        self.mark(self.a[0], grade="", state="insufficient_evidence")
        _, summary = validate_reviews(self.batch, self.save(self.a, "unknown.csv"), "A")
        self.assertEqual(summary["counts"]["insufficient_evidence"], 1)
        self.assertEqual(summary["eligible_completed"], 0)
        self.a[0]["relevance_0_1_2"] = "0"
        with self.assertRaises(ValueError):
            validate_reviews(self.batch, self.save(self.a, "forced_zero.csv"), "A")

    def test_agreement_hand_calculated_and_degenerate_cases(self):
        report = agreement([(0, 0), (1, 2), (2, 1)])
        self.assertAlmostEqual(report["exact_agreement"], 1/3)
        self.assertEqual(report["confusion_matrix"], [[1, 0, 0], [0, 0, 1], [0, 1, 0]])
        self.assertAlmostEqual(report["weighted_cohen_kappa"], 0.5)
        self.assertEqual(agreement([(0, 0), (1, 1), (2, 2)])["weighted_cohen_kappa"], 1)
        self.assertEqual(agreement([(2, 2), (2, 2)])["undefined_reason"], "zero_expected_disagreement")
        self.assertIsNone(agreement([])["weighted_cohen_kappa"])

    def test_comparison_excludes_ai_and_unresolved_preserves_originals(self):
        pairs = self.paired(4)
        for i, (a, b) in enumerate(pairs):
            self.mark(a, grade=str(i % 3)); self.mark(b, grade=str(i % 3))
        pairs[1][1]["relevance_0_1_2"] = "2"
        pairs[2][0]["annotation_origin"] = "ai_draft"
        self.mark(pairs[3][1], grade="", state="needs_review")
        ap, bp = self.save(self.a, "A.csv"), self.save(self.b, "B.csv")
        before = ap.read_bytes(), bp.read_bytes()
        out = self.folder / "comparison"
        report = compare_reviews(self.batch, ap, bp, out)
        self.assertEqual(report["agreement"]["eligible_pairs"], 2)
        self.assertEqual(report["agreement"]["exact_agreement"], 0.5)
        self.assertEqual(report["queue_counts"]["label_disagreement"], 1)
        self.assertEqual(report["adjudication_required"], 23)
        self.assertEqual(before, (ap.read_bytes(), bp.read_bytes()))
        self.assertEqual(before, ((out / "reviewer_A.original.csv").read_bytes(), (out / "reviewer_B.original.csv").read_bytes()))
        self.assertTrue(all(r["final_label"] == "" for r in read_csv(out / "adjudication.csv")))
        with self.assertRaises(FileExistsError):
            compare_reviews(self.batch, ap, bp, out)

    def test_same_reviewer_cannot_be_independent(self):
        a, b = self.paired(1)[0]
        self.mark(a); self.mark(b); b["annotator_id"] = a["annotator_id"].lower()
        with self.assertRaises(ValueError):
            compare_reviews(self.batch, self.save(self.a, "A.csv"), self.save(self.b, "B.csv"), self.folder / "bad")

    def test_adjudication_requires_third_person_and_preserves_two_reviews(self):
        a, b = self.paired(1)[0]; self.mark(a, "0"); self.mark(b, "2")
        out = self.folder / "comparison"
        compare_reviews(self.batch, self.save(self.a, "A.csv"), self.save(self.b, "B.csv"), out)
        rows = read_csv(out / "adjudication.csv")
        row = next(r for r in rows if r["pair_id"] == a["pair_id"])
        row.update(adjudicator_id="TEST_FAKE_THIRD_PERSON", annotation_origin="human_adjudicated", final_status="completed",
                   final_label="1", cv_evidence=row["cv_text"].splitlines()[0], jd_evidence=row["jd_text"].splitlines()[0],
                   adjudication_rationale="TEST ONLY fabricated adjudication, not gold", adjudicated_at="2026-11-12T15:00:00+07:00")
        def save_final():
            path = self.folder / "final.TEST_ONLY.csv"
            with path.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(row)); w.writeheader(); w.writerows(rows)
            return path
        self.assertEqual(validate_adjudication(out, save_final())["statuses"]["completed"], 1)
        row["adjudicator_id"] = a["annotator_id"]
        with self.assertRaises(ValueError):
            validate_adjudication(out, save_final())
        row["adjudicator_id"] = "TEST_FAKE_THIRD_PERSON"; row["A_relevance_0_1_2"] = "1"
        with self.assertRaises(ValueError):
            validate_adjudication(out, save_final())

    def test_empty_adjudication_queue_is_valid(self):
        for a, b in self.paired(24):
            self.mark(a, "1"); self.mark(b, "1")
        out = self.folder / "all_agree"
        report = compare_reviews(self.batch, self.save(self.a, "A.csv"), self.save(self.b, "B.csv"), out)
        self.assertEqual(report["adjudication_required"], 0)
        self.assertEqual(validate_adjudication(out, out / "adjudication.csv")["total"], 0)

    def test_original_packet_tampering_detected(self):
        path = self.batch / "reviewer_A/review.csv"
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaises(ValueError):
            load_batch(self.batch)
