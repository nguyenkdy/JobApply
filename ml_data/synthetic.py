"""Render authored fictional scenarios; no JD, ranking or label input."""
from collections import Counter
import json
from pathlib import Path
import re
import shutil

from .common import (MIN_PROFESSIONAL_BODY_CHARS, digest, fresh_folder, normalize,
                     read_json, require, seal, write_csv, write_json)

FIELDS = ("cv_id", "cv_text", "source_group", "template_group", "is_synthetic", "role",
          "skills", "stack", "experience_json", "exposure", "text_scope", "lineage_json")
LAYOUTS = {
    "employment_history": ("Kinh nghiệm", "Công việc và công cụ", "Phạm vi trách nhiệm"),
    "personal_portfolio": ("1. Bài toán dự án", "2. Cách thực hiện", "3. Giới hạn kết quả"),
    "internship_log": ("Phân công thực tập", "Nhật ký thực hiện", "Phần cần hướng dẫn"),
    "incident_case": ("Bối cảnh và triệu chứng", "Điều tra / xử lý", "Rút kinh nghiệm"),
    "contract_handover": ("Phạm vi hợp đồng", "Sản phẩm bàn giao", "Điều kiện tiếp nhận"),
    "incomplete_account": ("Ghi chú hồ sơ", "Việc đã thực hiện", "Thông tin còn thiếu"),
}


def render_scenario(scenario, design):
    """Only transport explicit assertions; this is not an experience extractor."""
    sid, family, blocks = scenario["id"], scenario["family"], scenario["blocks"]
    require(re.fullmatch(r"CVX_[A-Z]{2}_\d{2}", sid), "Invalid stable scenario ID")
    require(family in design["families"] and family in LAYOUTS, "Unknown template family")
    require(scenario["role"] in design["roles"], "Unknown role")
    require(len(blocks) == 3 and all(isinstance(b, str) and b.strip() for b in blocks), "Three authored blocks required")
    text = "\n\n".join(f"{heading}\n{body}" for heading, body in zip(LAYOUTS[family], blocks))
    require(len(normalize(text)) >= MIN_PROFESSIONAL_BODY_CHARS, "CV too short")

    def evidence(index):
        require(type(index) is int and 0 <= index < len(blocks), "Invalid evidence block")
        quote = blocks[index]
        start = text.index(quote)
        return dict(quote=quote, start=start, end=start + len(quote))

    skill_evidence = {}
    for skill, index in scenario["skills"].items():
        item = evidence(index)
        require(re.search(r"(?<!\w)" + re.escape(skill) + r"(?!\w)", item["quote"], re.IGNORECASE),
                f"Skill has no literal evidence: {sid}/{skill}")
        skill_evidence[skill] = item
    require(set(scenario["stack"]) <= set(skill_evidence), "Stack requires skill evidence")
    duration, months, duration_evidence = scenario["duration"], {}, []
    if duration is not None:
        item = evidence(duration["block"])
        require(duration["kind"] in {"employment", "project", "internship", "contract"}, "Unknown experience kind")
        require(type(duration["months"]) is int and duration["months"] > 0, "Unknown duration must be null, not zero")
        require(duration["scope"].casefold() in item["quote"].casefold()
                and re.search(r"(?<!\d)" + str(duration["months"]) + r" tháng(?!\w)", item["quote"]),
                f"Duration lacks explicit scope/month evidence: {sid}")
        months[duration["scope"]] = duration["months"]
        duration_evidence.append(dict(scope=duration["scope"], months=duration["months"],
                                      kind=duration["kind"], **item))
    lineage = dict(scenario_id=sid, generation_version=design["version"],
                   generation_cohort=design["generation_cohort"], author=design["author"],
                   method="individually authored career scenario; deterministic rendering; no target JD or ranking",
                   template_family=family, parent_ids=[],
                   variant_history=[dict(version=1, action="initial authored scenario", date=design["created_on"])],
                   experience_kind=duration["kind"] if duration else "unknown",
                   evidence_status="synthetic_author_assertion; not independent professional verification")
    row = dict(cv_id=sid, cv_text=text, source_group="scenario:" + sid,
               template_group=design["version"] + ":" + family, is_synthetic="true", role=scenario["role"],
               skills=";".join(scenario["skills"]), stack=";".join(scenario["stack"]),
               experience_json=json.dumps(months, ensure_ascii=False, sort_keys=True),
               exposure="prospective", text_scope="professional", lineage_json=json.dumps(lineage, ensure_ascii=False, sort_keys=True))
    receipt = dict(cv_id=sid, cv_text_sha256=digest(text), skills=skill_evidence,
                   stack={s: skill_evidence[s] for s in scenario["stack"]}, durations=duration_evidence,
                   unknown_duration=duration is None, lineage=lineage)
    return row, receipt


def render_batch(assets, output):
    assets = Path(assets).resolve()
    design, scenarios = read_json(assets / "design.json"), read_json(assets / "scenarios.json")
    require(len(scenarios) == design["expected_count"], "Scenario count differs from declared design")
    require(len({s["id"] for s in scenarios}) == len(scenarios), "Duplicate scenario IDs")
    require(Counter(s["role"] for s in scenarios) == {r: design["per_role"] for r in design["roles"]}, "Role quota mismatch")
    require(all(sum(s["role"] == role and s["family"] == family for s in scenarios) == 2
                for role in design["roles"] for family in design["families"]), "Each role/family requires two authored scenarios")
    rendered = [render_scenario(s, design) for s in sorted(scenarios, key=lambda s: s["id"])]
    folder = fresh_folder(output, (assets,))
    for name in ("design.json", "scenarios.json"):
        shutil.copyfile(assets / name, folder / name)
    write_csv(folder / "cvs.csv", [row for row, _ in rendered], FIELDS)
    write_json(folder / "evidence.json", [item for _, item in rendered])
    summary = dict(cv_count=len(rendered), source_groups=len({row["source_group"] for row, _ in rendered}),
                   template_groups=len({row["template_group"] for row, _ in rendered}),
                   roles=dict(Counter(row["role"] for row, _ in rendered)),
                   experience_kinds=dict(Counter(item["lineage"]["experience_kind"] for _, item in rendered)),
                   is_synthetic=True, exposure="prospective", labels_created=0,
                   limitation="One AI author/cohort; template-disjoint is not independent real-applicant validation")
    write_json(folder / "summary.json", summary)
    seal(folder, "synthetic-cvs", dict(generation_version=design["version"], generation_cohort=design["generation_cohort"]))
    return summary
