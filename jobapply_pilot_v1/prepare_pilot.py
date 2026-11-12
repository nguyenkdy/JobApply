#!/usr/bin/env python3
"""Rebuild the fixed pilot and synthetic CVs. No relevance labels are generated."""
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

CVS = [
    {"cv_id":"CV_SYN_01", "target_role":"Backend Python", "experience_months":24,
     "professional_summary":"Backend Developer Python/Django, 2 năm kinh nghiệm phát triển ứng dụng web.",
     "skills_text":"Python, Django, Django REST Framework, PostgreSQL, SQL, Redis, Git, Docker, pytest.",
     "experience_text":"Xây dựng REST API cho hệ thống quản lý đơn hàng. Thiết kế cơ sở dữ liệu PostgreSQL, tối ưu truy vấn SQL, xử lý xác thực và phân quyền. Viết unit test bằng pytest, sửa lỗi và review code trong nhóm Agile. Đóng gói ứng dụng bằng Docker và sử dụng Git để quản lý mã nguồn.",
     "projects_text":"Dự án giả lập: API quản lý sản phẩm và đơn hàng bằng Django, PostgreSQL; cache bằng Redis; kiểm thử API tự động.",
     "professional_language":"Đọc hiểu tài liệu kỹ thuật và giao tiếp công việc bằng tiếng Anh."},
    {"cv_id":"CV_SYN_02", "target_role":"Data Analyst", "experience_months":24,
     "professional_summary":"Data Analyst, 2 năm kinh nghiệm phân tích dữ liệu kinh doanh và xây dựng báo cáo.",
     "skills_text":"Python, pandas, SQL, SQL Server, Power BI, DAX, Excel, data visualization, statistics.",
     "experience_text":"Làm sạch dữ liệu bán hàng bằng Python và pandas. Viết SQL tổng hợp chỉ số doanh thu, phân tích hành vi khách hàng và theo dõi KPI. Xây dựng dashboard Power BI, mô hình dữ liệu và báo cáo định kỳ. Trao đổi với bộ phận kinh doanh để giải thích kết quả phân tích.",
     "projects_text":"Dự án giả lập: dashboard doanh thu, phân tích tỷ lệ giữ chân khách hàng, tự động hóa cập nhật báo cáo từ SQL Server.",
     "professional_language":"Đọc hiểu tài liệu và trình bày kết quả công việc bằng tiếng Anh."},
    {"cv_id":"CV_SYN_03", "target_role":"Backend Java", "experience_months":36,
     "professional_summary":"Backend Developer Java, 3 năm kinh nghiệm xây dựng dịch vụ web.",
     "skills_text":"Java, Spring Boot, Hibernate, JPA, MySQL, SQL, REST API, Kafka, Git, Docker, JUnit, Maven.",
     "experience_text":"Phát triển microservices quản lý thanh toán bằng Java và Spring Boot. Thiết kế API, tích hợp dịch vụ qua Kafka, tối ưu truy vấn MySQL. Áp dụng OOP, design patterns, viết unit test JUnit và tham gia code review. Làm việc theo Scrum và triển khai qua pipeline CI/CD.",
     "projects_text":"Dự án giả lập: dịch vụ thanh toán và đối soát, có kiểm thử tự động và tài liệu API bằng Swagger.",
     "professional_language":"Giao tiếp công việc bằng tiếng Anh."},
    {"cv_id":"CV_SYN_04", "target_role":"Frontend", "experience_months":12,
     "professional_summary":"Junior Frontend Developer, 1 năm kinh nghiệm phát triển giao diện web với React.",
     "skills_text":"React, JavaScript, TypeScript, HTML5, CSS3, Redux, Git, REST API, Jest, responsive design.",
     "experience_text":"Xây dựng giao diện quản lý bán hàng bằng React và TypeScript. Tạo component tái sử dụng, quản lý state bằng Redux, tích hợp REST API. Viết kiểm thử component, sửa lỗi giao diện trên các trình duyệt và tối ưu bố cục responsive. Phối hợp với designer và backend developer.",
     "projects_text":"Dự án giả lập: dashboard quản lý đơn hàng có tìm kiếm, phân trang và biểu đồ; kiểm thử bằng Jest.",
     "professional_language":"Đọc hiểu tài liệu kỹ thuật tiếng Anh."},
    {"cv_id":"CV_SYN_05", "target_role":"DevOps / Cloud", "experience_months":24,
     "professional_summary":"DevOps Engineer, 2 năm kinh nghiệm vận hành ứng dụng trên Linux và AWS.",
     "skills_text":"Linux, Bash, Python, Docker, Kubernetes, AWS, Terraform, Jenkins, Git, Prometheus, Grafana, CI/CD, DNS, networking.",
     "experience_text":"Xây dựng pipeline Jenkins để kiểm thử và triển khai ứng dụng Docker lên Kubernetes. Cấp phát hạ tầng AWS bằng Terraform. Giám sát hệ thống với Prometheus và Grafana; xử lý sự cố mạng, DNS và container. Viết Bash và Python để tự động hóa tác vụ vận hành.",
     "projects_text":"Dự án giả lập: triển khai ứng dụng microservices với CI/CD, giám sát CPU, RAM, lỗi và cảnh báo. Chưa có chứng chỉ cloud chuyên sâu.",
     "professional_language":"Giao tiếp công việc và đọc tài liệu bằng tiếng Anh."},
    {"cv_id":"CV_SYN_06", "target_role":"QA / Testing", "experience_months":24,
     "professional_summary":"QA Automation Engineer, 2 năm kinh nghiệm kiểm thử ứng dụng web và API.",
     "skills_text":"Python, Selenium, pytest, Postman, API testing, SQL, Jira, Git, Jenkins, regression testing.",
     "experience_text":"Phân tích yêu cầu, viết test case, kiểm thử hồi quy và báo lỗi trên Jira. Viết script Python với Selenium để kiểm thử giao diện và dùng pytest kiểm thử REST API. Chuẩn bị dữ liệu test bằng SQL, tích hợp kiểm thử tự động vào Jenkins và phối hợp với developer để tái hiện lỗi.",
     "projects_text":"Dự án giả lập: bộ kiểm thử tự động đăng nhập, giỏ hàng và thanh toán cho ứng dụng web.",
     "professional_language":"Đọc tài liệu và trao đổi lỗi bằng tiếng Anh."},
]

DROP_PATTERNS = [
    (r"ưu tiên các ứng viên trẻ từ\s*\d{4}", "birth_year_preference"),
    (r"non[- ]smoker", "non_professional_personal_condition"),
    (r"^working hours & location$", "logistics_heading"),
    (r"^development is the largest discipline at", "company_marketing"),
    (r"^we are a growing software development company", "company_marketing"),
    (r"thấu hiểu sứ mệnh và giá trị của", "company_brand_value_statement"),
    (r"^any personal data you share", "privacy_notice"),
    (r"^to help us have a good understanding about your competencies", "application_instructions"),
    (r"skills tags:", "redundant_source_tags"),
    (r"^(?:The Brilliant Career You Love|Are you passionate about innovative|Do you dream of being part|"
     r"Would you love to work in one|If your answer is yes|This vacancy is an ideal opportunity|"
     r"As an intern at KMS Healthcare)", "company_marketing_or_redundant_intro"),
]
TITLE_EDITS = {
    "job_9a6c25a9e0775da6a725": "Frontend Engineer (Chinese-speaking)",
    "job_7aff0f0a326b3c874236": "Junior Frontend Developer",
    "job_f8b5f70d8b4ae8757d1c": "Manual Tester",
}


def write_csv(path, records, fields=None):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields or list(records[0]))
        w.writeheader()
        w.writerows(records)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--matching", type=Path, required=True)
    ap.add_argument("--clean", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, default=Path(__file__).with_name("selection_manifest.csv"))
    ap.add_argument("--output-dir", type=Path, default=Path(__file__).parent)
    args=ap.parse_args()
    def read(p):
        with p.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
    source={r["job_id"]:r for r in read(args.matching)}
    raw={r["job_id"]:r for r in read(args.clean)}
    manifest=read(args.manifest)
    jobs,edits=[],[]
    for entry in manifest:
        jid=entry["job_id"]
        r=dict(source[jid])
        if jid=="job_db7d95cf020eb5437f89":
            # Restore real source responsibilities omitted by the section parser.
            intro=raw[jid]["description"].split("Your skills and experience:")[0].strip().splitlines()
            # Omit the opening company/location paragraph, retain the actual tasks.
            r["tasks_text"]="\n".join(intro[1:]).strip()
            edits.append({"job_id":jid,"field":"tasks_text","action":"restore_source_lines",
                "reason":"missing_tasks_section","before":"","after":r["tasks_text"]})
        if jid in TITLE_EDITS:
            edits.append({"job_id":jid,"field":"title_for_matching","action":"remove_metadata",
                "reason":"salary_location_or_company_in_title","before":r["title_for_matching"],"after":TITLE_EDITS[jid]})
            r["title_for_matching"]=TITLE_EDITS[jid]
        for field in ["tasks_text","requirements_text","preferred_requirements_text"]:
            kept=[]
            for line in r[field].splitlines():
                reason=next((reason for pattern,reason in DROP_PATTERNS if re.search(pattern,line,re.I)),None)
                if reason:
                    edits.append({"job_id":jid,"field":field,"action":"remove_line","reason":reason,"before":line,"after":""})
                    continue
                # A technical responsibility can mention its employer; remove only that employer clause.
                if jid=="job_23ea3536dd60e343f94d" and line.startswith("As a Senior Developer (Java) at Endava,"):
                    new=line.replace(" at Endava,", ",",1)
                    edits.append({"job_id":jid,"field":field,"action":"remove_metadata","reason":"employer_name","before":line,"after":new})
                    line=new
                kept.append(line)
            r[field]="\n".join(kept)
        sections=[("Chức danh",r["title_for_matching"]),("Nhiệm vụ",r["tasks_text"]),
            ("Yêu cầu",r["requirements_text"]),("Ưu tiên / Nice to have",r["preferred_requirements_text"])]
        match_text="\n\n".join(label+":\n"+text for label,text in sections if text)
        jobs.append({"job_id":jid,"pilot_group":entry["pilot_group"],"title":r["title"],
            "title_for_matching":r["title_for_matching"],"company":r["company"],"site":r["site"],
            "job_url":r["job_url"],"content_group_id":r["content_group_id"],
            "tasks_text":r["tasks_text"],"requirements_text":r["requirements_text"],
            "preferred_requirements_text":r["preferred_requirements_text"],"match_text":match_text,
            "review_status":"assistant_screened_pilot_not_human_gold",
            "selection_reason":entry["selection_reason"],"source_match_text_sha256":hashlib.sha256(source[jid]["match_text"].encode()).hexdigest()})
    assert len(jobs)==50 and len({r["job_id"] for r in jobs})==50
    assert len({r["content_group_id"] for r in jobs})==50
    assert all(len(r["requirements_text"])>100 and len(r["tasks_text"])>100 for r in jobs)
    for r in jobs:
        assert not re.search(r"ứng viên trẻ từ\s*\d{4}|giới tính|độ tuổi|\d{2}\s*tuổi",r["match_text"],re.I)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    write_csv(args.output_dir/"jobs_pilot.csv",jobs)
    write_csv(args.output_dir/"pilot_edits.csv",edits,["job_id","field","action","reason","before","after"])
    cvs=[]
    cv_dir=args.output_dir/"synthetic_cv_texts"
    cv_dir.mkdir(exist_ok=True)
    for original in CVS:
        r=dict(original)
        # Only professional content is assembled; no personal metadata fields exist.
        r["cv_text"]="\n".join(r[f] for f in ["professional_summary","skills_text","experience_text","projects_text","professional_language"])
        r["is_synthetic"]=True
        cvs.append(r)
        (cv_dir/(r["cv_id"]+".txt")).write_text(r["cv_text"],encoding="utf-8")
    write_csv(args.output_dir/"cvs_synthetic.csv",cvs)
    print(f"Prepared {len(jobs)} JDs, {len(cvs)} synthetic CVs, {len(edits)} logged text edits.")


if __name__=="__main__":main()
