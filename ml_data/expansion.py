"""Combine a frozen upstream v2 with synthetic CVs and report a known-JD preview."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import subprocess

from .common import (ROOT, file_hash, fresh_folder, read_json, read_lines, require,
                     seal, verify, write_json)
from .ingest import ingest
from .sampling import choose_mixed
from .splitting import PARTITIONS, audit_split, make_split

CV_COLUMNS = dict(external_id="cv_id", text="cv_text", source_group="source_group",
                  template_group="template_group", is_synthetic="is_synthetic", role="role",
                  skills="skills", stack="stack", experience="experience_json", exposure="exposure",
                  text_scope="text_scope", lineage="lineage_json")


def assert_frozen_jd(before, after):
    """Compare full records, including raw rows, decisions, lineage and group exposure."""
    old = {r["record_id"]: r for r in before if r["kind"] == "jd"}
    new = {r["record_id"]: r for r in after if r["kind"] == "jd"}
    require(old and old == new, "Frozen JD changed during combined import; do not publish split")
    return dict(records=len(old), all_fields_identical=True,
                development_records=sum(r["development_only"] for r in old.values()))


def protected_inputs(upstream):
    summary = read_json(upstream / "summary.json")
    hashes = {}
    for name, expected in summary["source_hashes"].items():
        require(file_hash(ROOT / name) == expected, "Original CSV differs from frozen upstream: " + name)
        hashes[name] = expected
    tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--", "jobapply_pilot_v1"],
                             capture_output=True, text=True, check=True).stdout.splitlines()
    require(tracked, "Cannot inventory protected pilot inputs")
    hashes.update({name: file_hash(ROOT / name) for name in tracked})
    return hashes


def workload_and_distribution(records, assignments, seed):
    by_id = {r["record_id"]: r for r in records}
    jobs = [by_id[a["record_id"]] for a in assignments if a["kind"] == "jd" and a["partition"] == "shared"]
    require(all(j["decision"] == "keep" and not j["development_only"] for j in jobs), "Ineligible JD in catalogue")
    distributions, counts, strategies, shortages = {}, {}, Counter(), []
    all_kinds = {r["lineage"]["experience_kind"] for r in records if r["kind"] == "cv"}
    for partition in PARTITIONS:
        cvs = [by_id[a["record_id"]] for a in assignments if a["kind"] == "cv" and a["partition"] == partition]
        kinds = Counter(r["lineage"]["experience_kind"] for r in cvs)
        scoped_months = Counter(f"{r['lineage']['experience_kind']}:{scope}:{months}"
                               for r in cvs for scope, months in r["experience"].items())
        distributions[partition] = dict(cv_count=len(cvs), cv_ids=sorted(r["external_id"] for r in cvs),
            roles=dict(Counter(r["role"] for r in cvs)), source_groups=len({r["source_group"] for r in cvs}),
            group_count=len({r["group_id"] for r in cvs}),
            template_families=dict(Counter(r["lineage"]["template_family"] for r in cvs)),
            experience_kinds=dict(kinds), scoped_months=dict(scoped_months),
            missing_experience_kinds=sorted(all_kinds - set(kinds)), jd_catalogue_count=len(jobs))
        if partition != "train":
            counts[partition] = len(cvs) * len(jobs)
        else:
            count = 0
            for cv in cvs:
                chosen, missing = choose_mixed(cv, jobs, "train", seed, 3, 2)
                count += len(chosen)
                strategies.update(chosen.values())
                shortages.extend(missing)
            counts[partition] = count
    return dict(distributions=distributions, workload=dict(
        random_per_train_cv=3, hard_per_type=2, hard_types=3,
        train_requested_upper_bound=distributions["train"]["cv_count"] * min(len(jobs), 9),
        pairs_by_partition=counts, total_pairs=sum(counts.values()), train_by_strategy=dict(strategies),
        hard_shortage_cv_categories=len(shortages), unfilled_slots=sum(r["requested"] - r["selected"] for r in shortages),
        shortages=shortages, pair_files_created=0, labels_created=0,
        note="Exact count under current sampler/seed and metadata; validation/test census. Not a relevance estimate."),
        catalogue=dict(count=len(jobs), record_ids=sorted(j["record_id"] for j in jobs),
                       roles=dict(Counter(j["role"] or "unknown" for j in jobs)),
                       missing_metadata={field: sum(not j[field] for j in jobs) for field in ("skills", "stack", "experience")}))


def prepare_expansion(upstream, cv_batch, output, seed=20261113):
    upstream, cv_batch = Path(upstream).resolve(), Path(cv_batch).resolve()
    verify(upstream, "upstream")
    verify(upstream / "dataset", "dataset")
    verify(cv_batch, "synthetic-cvs")
    old_config = read_json(upstream / "import_config.json")
    require(old_config.get("adapter_version") == "upstream-observation-v2", "Require an actual frozen upstream v2")
    require(len(old_config["sources"]) == 1 and old_config["sources"][0]["kind"] == "jd", "Expected one canonical JD source")
    before = protected_inputs(upstream)
    folder = fresh_folder(output, (upstream, cv_batch))
    config = deepcopy(old_config)
    config["dataset_version"] = "synthetic-careers-v1-jd-v2-" + file_hash(cv_batch / "cvs.csv")[:12]
    for item in config["sources"] + config["context_files"]:
        item["path"] = str((upstream / item["path"]).resolve())
    config["sources"].append(dict(path=str(cv_batch / "cvs.csv"), kind="cv", namespace="jobapply-synthetic-careers-v1",
                                  version="sha256:" + file_hash(cv_batch / "manifest.json"), columns=CV_COLUMNS,
                                  source_url=None, collected_at=None,
                                  usage_terms="New fictional task-authored assets; no real applicant identity"))
    for path, role in ((cv_batch / "evidence.json", "synthetic_assertion_evidence_not_gold"),
                       (cv_batch / "design.json", "generation_protocol"),
                       (cv_batch / "scenarios.json", "authored_scenario_source"),
                       (cv_batch / "manifest.json", "synthetic_batch_receipt"),
                       (upstream / "manifest.json", "frozen_upstream_receipt")):
        config["context_files"].append(dict(path=str(path), role=role))
    write_json(folder / "import_config.json", config)
    imported = ingest(folder / "import_config.json", folder / "dataset")
    records = read_lines(folder / "dataset/records.jsonl")
    frozen = assert_frozen_jd(read_lines(upstream / "dataset/records.jsonl"), records)
    require(read_lines(upstream / "dataset/protected_anchors.jsonl") == read_lines(folder / "dataset/protected_anchors.jsonl"),
            "Protected pilot anchors changed since upstream v2")
    make_split(folder / "dataset", folder / "preview_split", "known-jd", seed)
    audit = audit_split(folder / "dataset", folder / "preview_split")
    plan = workload_and_distribution(records, read_lines(folder / "preview_split/assignments.jsonl"), seed)
    groups = read_json(folder / "dataset/groups.json")
    cv_groups = [g for g in groups if g["kind"] == "cv"]
    cv_ids = {r["record_id"] for r in records if r["kind"] == "cv"}
    cv_edges = [e for e in read_lines(folder / "dataset/group_edges.jsonl") if e["left"] in cv_ids or e["right"] in cv_ids]
    require(before == protected_inputs(upstream), "Protected original inputs changed")
    verify(upstream, "upstream")
    verify(cv_batch, "synthetic-cvs")
    write_json(folder / "protected_input_hashes.json", before)
    report = dict(version="synthetic-known-jd-preview-v1", protocol="known-jd", seed=seed, ranking_k=5,
                  dataset_version=config["dataset_version"], labels_created=0, final_test_ready=False,
                  cv_batch_summary=read_json(cv_batch / "summary.json"), import_summary=imported,
                  verification=dict(frozen_jd=frozen, source_csv_unchanged=3, pilot_tracked_files_unchanged=len(before)-3,
                    upstream_manifest_sha256=file_hash(upstream / "manifest.json"),
                    upstream_dataset_manifest_sha256=file_hash(upstream / "dataset/manifest.json"),
                    cv_batch_manifest_sha256=file_hash(cv_batch / "manifest.json"),
                    dataset_manifest_sha256=file_hash(folder / "dataset/manifest.json"),
                    split_manifest_sha256=file_hash(folder / "preview_split/manifest.json")),
                  cv_grouping=dict(groups=len(cv_groups), source_groups=len({r["source_group"] for r in records if r["kind"] == "cv"}),
                    template_groups=len({r["template_group"] for r in records if r["kind"] == "cv"}),
                    pilot_connected_groups=sum(bool(g["protected_pilot_ids"]) for g in cv_groups),
                    development_groups=sum(g["development_only"] for g in cv_groups),
                    edge_reasons=dict(Counter(e["reason"] for e in cv_edges))),
                  split_audit=audit, **plan,
                  data_analyst=read_json(upstream / "summary.json")["data_analyst_accounting"],
                  limitations=["Synthetic author assertions; no relevance labels or independent professional review",
                    "One generation cohort; template groups do not imply independent real applicants",
                    "Only six template groups; inspect experience-kind coverage before treating any partition as an evaluation set",
                    "Known-JD measures new CV on a shared frozen catalogue, not generalization to new JD",
                    "Lexical dedup does not guarantee absence of semantic paraphrases",
                    "CVs later used to tune parsers/features must become development with their whole family",
                    "Data Analyst remains in research scope; repair/review JD on development and obtain fresh usable JD before its benchmark"])
    write_json(folder / "preview_report.json", report)
    (folder / "preview_report.md").write_text(render_report(report), encoding="utf-8", newline="\n")
    seal(folder, "cv-jd-preview", dict(seed=seed, mode="known-jd", final_test_ready=False))
    return {k: report[k] for k in ("cv_grouping", "split_audit", "workload", "verification")}


def render_report(report):
    """Human handoff generated exclusively from verified run data."""
    d, w, c = report["distributions"], report["workload"], report["catalogue"]
    rows = "\n".join(f"| {p} | {d[p]['cv_count']} | {d[p]['group_count']} | {d[p]['jd_catalogue_count']} | {w['pairs_by_partition'][p]} |"
                     for p in PARTITIONS)
    details = "\n\n".join(f"**{p}:** nghề `{d[p]['roles']}`; họ `{d[p]['template_families']}`; loại kinh nghiệm `{d[p]['experience_kinds']}`. Thiếu loại `{d[p]['missing_experience_kinds']}`."
                          for p in PARTITIONS)
    dec = report["import_summary"]["distribution"]["jd"]["decisions"]
    return f"""# Preview CV synthetic + JD v2 — 13/11/2026

Báo cáo sinh từ `preview_report.json` của run đã xác minh, seed {report['seed']}, protocol known-jd, Top 5. Không train, không tạo nhãn/cặp chấm, không khóa final test. Không chạy lại upstream, chọn lô JD hoặc pilot để cải thiện điểm.

Đã tạo {report['cv_batch_summary']['cv_count']} CV synthetic, 12 cho mỗi nhóm Backend Python, Backend Java, Frontend, DevOps/Cloud và QA/Testing. Có {report['cv_grouping']['source_groups']} nguồn kịch bản riêng nhưng chỉ {report['cv_grouping']['groups']} nhóm khung độc lập theo kiểm tra lineage; tất cả cùng một đợt tác giả AI. Không phải 60 ứng viên thật độc lập. Tất cả metadata là khẳng định của người viết kịch bản, chưa được chuyên gia xác minh.

JD giữ nguyên toàn bộ record v2: {dec.get('keep', 0)} keep, {dec.get('exclude_exact_duplicate', 0)} bản trùng loại, {dec.get('quarantine', 0)} quarantine. Catalog thực sự dùng chung là {c['count']} JD keep ngoài development; 100 keep development không tham gia. Closure development được giữ nguyên {report['verification']['frozen_jd']['development_records']} record kể cả cách ly/trùng. Không bỏ dữ liệu khỏi snapshot để xử lý lỗi.

| Partition preview | CV | Nhóm CV | JD dùng chung | Cặp dự kiến |
|---|---:|---:|---:|---:|
{rows}

{details}

Tỷ lệ đích 60/20/20 áp lên nguyên nhóm; phân bố thực tế ở bảng trên. Giữ họ nguyên vẹn gây lệch loại kinh nghiệm; chưa đủ để coi preview là benchmark cân đối. Không đổi seed, tách họ hoặc đổi provenance để ép tỷ lệ. Known-jd chỉ đo CV mới trên kho JD đã biết, không đo tổng quát hóa sang JD mới.

Train dự kiến 3 random + tối đa 2 cho mỗi loại hard/CV: trần {w['train_requested_upper_bound']} cặp, hiện lấy được {w['pairs_by_partition']['train']}; chiến lược thực tế `{w['train_by_strategy']}`. Thiếu {w['unfilled_slots']} slot theo metadata hiện có. Catalog thiếu metadata `{c['missing_metadata']}` nên chưa thể lấy hard candidates có bằng chứng bằng sampler hiện tại. Không mặc định cặp khó là nhãn 0. Validation/test sẽ chấm toàn catalog: tổng cả ba partition {w['total_pairs']} cặp theo kế hoạch hiện tại, chưa tạo file cặp hay nhãn. Có metadata JD mới thì phải version dataset và tính lại, không tự nâng cấp cohort đã dùng sửa parser thành prospective.

Kiểm tra cấu trúc leakage: `{report['split_audit']['leakage_check_passed']}`; CV nối pilot: {report['cv_grouping']['pilot_connected_groups']} nhóm. Quyết định CV: `{report['import_summary']['distribution']['cv']['decisions']}`. Near duplicate chỉ là Jaccard 3 token ≥0,85, không chứng nhận độc lập ngữ nghĩa. Kiểm tra giữ nguyên byte: 3 CSV và {report['verification']['pilot_tracked_files_unchanged']} file pilot theo Git; toàn bộ record JD bằng nhau cả text, quality flags, lineage, group/exposure và raw row.

**Data Analyst vẫn thuộc mục tiêu nghiên cứu:** {report['data_analyst']['source_tagged']} tag nguồn, {report['data_analyst']['title_cued']} dấu hiệu chức danh, {report['data_analyst']['pilot_related']} nối pilot; {report['data_analyst']['nonpilot_gate_passing']} ngoài pilot qua gate. Bốn JD đã dành sửa parser vẫn development/quarantine. Cần rà lại nguồn/các section lỗi hoặc bổ sung JD mới có provenance trước khi thêm CV/benchmark Data Analyst; không thay đổi JD hiện tại để đủ quota.

**Cần làm tiếp:** bổ sung metadata JD có evidence; có chuyên môn rà độ hợp lý của CV và quy tắc gán nhãn; bổ sung các họ CV mới đa dạng loại kinh nghiệm nếu cần đánh giá cân đối; sau đó quyết định split và khối lượng chấm. Nếu dùng CV hiện tại sửa parser/feature, chuyển cả họ sang development ở phiên bản sau. Chưa triển khai vòng hai reviewer. Dữ liệu synthetic và nhãn nội bộ sau này không tự chứng minh chất lượng trên người dùng thật.
"""
