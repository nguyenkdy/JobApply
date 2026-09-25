"""Idempotent local demo data, exclusively through authenticated service APIs."""

import io
import os
from datetime import datetime, timedelta, timezone
import httpx
from pypdf import PdfWriter

PASSWORD = "DemoJobApply123!"
URLS = {
    name: os.environ.get(f"{name.upper()}_SERVICE_URL", f"http://127.0.0.1:{port}")
    for name, port in [("account", 8001), ("job", 8002), ("application", 8003)]
}


def request(service, path, token=None, method="GET", **kwargs):
    response = httpx.request(
        method,
        URLS[service] + path,
        headers={"Authorization": f"Bearer {token}"} if token else {},
        timeout=20,
        **kwargs,
    )
    response.raise_for_status()
    return response.json()


def account(email, name, role):
    registration = httpx.post(
        URLS["account"] + "/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": name, "role": role},
        timeout=20,
    )
    if registration.status_code not in (201, 409):
        registration.raise_for_status()
    return request("account", "/auth/login", method="POST", json={"email": email, "password": PASSWORD})["access_token"]


def seed():
    candidate = account("candidate@example.com", "Nguyễn Minh Anh", "Candidate")
    profile = request("account", "/me", candidate)
    if not profile["bio"]:
        request(
            "account",
            "/me",
            candidate,
            "PUT",
            json={
                "full_name": profile["full_name"],
                "bio": "Ứng viên demo yêu thích phát triển sản phẩm web. Toàn bộ thông tin là dữ liệu giả.",
                "skills": ["Python", "React", "PostgreSQL"],
                "location": "Hồ Chí Minh",
                "contact": "Thông tin liên hệ demo",
            },
        )
    if not request("account", "/cvs", candidate):
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        writer.add_metadata({"/Title": "JobApply - Fictional demo CV", "/Author": "Demo candidate"})
        output = io.BytesIO()
        writer.write(output)
        request(
            "account",
            "/cvs",
            candidate,
            "POST",
            data={"name": "CV demo — dữ liệu giả"},
            files={"file": ("demo.pdf", output.getvalue(), "application/pdf")},
        )
    companies = [
        (
            "recruiter@example.com",
            "Trần Hoàng Nam",
            "NovaTech",
            "Hồ Chí Minh",
            [
                ("Python Backend Developer", "Middle", "Hybrid", "25–40 triệu / tháng"),
                ("Frontend Developer (React)", "Junior", "Onsite", "15–25 triệu / tháng"),
                ("Senior Fullstack Engineer", "Senior", "Remote", "40–60 triệu / tháng"),
                ("Thực tập sinh Software Engineer", "Intern", "Onsite", "5–8 triệu / tháng"),
            ],
        ),
        (
            "studio@example.com",
            "Lê Mai Chi",
            "Pixel Studio",
            "Hà Nội",
            [
                ("Product Designer (UI/UX)", "Middle", "Hybrid", "22–35 triệu / tháng"),
                ("Design Team Lead", "Lead", "Onsite", "Thỏa thuận"),
            ],
        ),
        (
            "data@example.com",
            "Phạm Quốc Huy",
            "GreenData",
            "Đà Nẵng",
            [
                ("Data Engineer — Python & SQL", "Junior", "Remote", "18–28 triệu / tháng"),
                ("Senior Data Analyst", "Senior", "Hybrid", "30–45 triệu / tháng"),
            ],
        ),
    ]
    for email, name, company_name, location, jobs in companies:
        token = account(email, name, "Recruiter")
        if not request("job", "/companies/mine", token):
            request(
                "job",
                "/companies",
                token,
                "POST",
                json={
                    "name": company_name,
                    "description": f"{company_name} là công ty giả lập cho đồ án JobApply. Chúng tôi xây dựng sản phẩm số, đề cao tinh thần hợp tác và tạo không gian để mỗi thành viên phát triển.\nMôi trường làm việc cởi mở, thời gian linh hoạt và cơ hội học hỏi từ những dự án thực tế.",
                    "location": location,
                    "website": "https://example.com",
                },
            )
        existing = {job["title"] for job in request("job", "/jobs/mine", token)}
        for title, level, mode, salary in jobs:
            if title in existing:
                continue
            job = request(
                "job",
                "/jobs",
                token,
                "POST",
                json={
                    "title": title,
                    "location": location,
                    "level": level,
                    "work_mode": mode,
                    "salary": salary,
                    "deadline": (datetime.now(timezone.utc) + timedelta(days=60)).isoformat(),
                    "description": "Tham gia phát triển sản phẩm cùng đội ngũ đa chức năng.\n• Phân tích yêu cầu và đề xuất giải pháp phù hợp.\n• Triển khai, kiểm thử và cải thiện chất lượng sản phẩm.\n• Chia sẻ kiến thức và phối hợp với đồng đội.\n\nQuyền lợi: thời gian linh hoạt, ngân sách học tập và môi trường tôn trọng ý kiến cá nhân.",
                    "requirements": "Có nền tảng chuyên môn phù hợp với vị trí.\nKhả năng tư duy logic, chủ động học hỏi và giao tiếp rõ ràng.\nCó dự án cá nhân hoặc kinh nghiệm thực tế là một lợi thế.\nĐây là tin tuyển dụng giả lập, chỉ dùng cho demo local.",
                },
            )
            request("job", f"/jobs/{job['id']}/status", token, "PATCH", json={"status": "Published"})
    print("Seed hoàn tất: candidate@example.com / recruiter@example.com (mật khẩu demo trong README).")


if __name__ == "__main__":
    seed()
