"""Deterministic, evidence-backed JD metadata extractor tuned and evaluated on development JDs."""
from collections import Counter
import json
from pathlib import Path
import re

from .common import (ROOT, csv_rows, file_hash, fresh_folder,
                     read_lines, require, seal, write_csv, write_json)
from .upstream import ERROR_CELL

EXTRACTOR_VERSION = "jd-rule-extractor-v3-clause-evidence"
CORE_FIELDS = ("title_for_matching", "requirements_text", "tasks_text")
BENCHMARK_ROLES = ("Backend Python", "Backend Java", "Frontend", "DevOps/Cloud", "QA/Testing")

TITLE_ROLE_PATTERNS = (
    ("Data Analyst", r"\b(?:data\s+analy(?:st|tics)|bi\s+analyst|business\s+intelligence\s+analyst|mis\s+specialist)\b|phân\s+tích\s+dữ\s+liệu"),
    ("QA/Testing", r"\b(?:qa|qc|tester|test\s+engineer|quality\s+assurance|quality\s+control|quality\s+engineer|automation\s+(?:test(?:er|ing)?|software\s+engineer)|manual\s+test(?:er|ing)?|pqa)\b|kiểm\s+thử"),
    ("DevOps/Cloud", r"\b(?:devops|devsecops|secops|site\s+reliability|sre|cloud\s+(?:engineer|architect)|infrastructure\s+engineer|platform\s+engineer(?:ing)?|(?<!bridge\s)system\s+(?:administrator|engineer)(?!\s*\([^)]*embedded)|it\s+system\s+admin(?:istrator)?|system\s+development\s*&\s*operations|system/\s*network|sysadmin|lập\s+trình\s+viên\s+aws|kỹ\s+sư\s+hệ\s+thống|vận\s+hành\s+hệ\s+thống)\b"),
    ("Frontend", r"\b(?:front[\s\-]?end|(?:react(?:\s*\.?\s*js)?(?!\s+native)|vue(?:\s*\.?\s*js)?|angular|next(?:\s*\.?\s*js)?)\s+(?:developer|engineer|dev)|ui[\s/]*fe\s+developer|web\s+front[\s\-]?end)\b"),
    ("Backend Python", r"\b(?:python|django|fastapi|flask|odoo)\b[^\n]*\b(?:backend|back[\s\-]?end|software|web|microservices|developer|engineer|dev|programmer|lập\s+trình)\b|\b(?:backend|back[\s\-]?end|software\s+engineer|developer|engineer|dev|lập\s+trình\s+viên|chuyên\s+viên\s+phát\s+triển\s+phần\s+mềm)\b[^\n]*\b(?:python|django|fastapi|flask|odoo)\b"),
    ("Backend Java", r"\b(?:java(?!\s*script)|spring(?:\s+boot)?|j2ee|kotlin)\b[^\n]*\b(?:backend|back[\s\-]?end|software|web|technical|developer|engineer|dev|lead|programmer|lập\s+trình)\b|\b(?:backend|back[\s\-]?end|software\s+engineer|developer|engineer|dev|lập\s+trình\s+viên|developer\s+manager)\b[^\n]*\b(?:java(?!\s*script)|spring(?:\s+boot)?)\b"),
)

OTHER_TITLE_ROLES = (
    ("Data Engineer", r"\bdata\s+engineer(?:ing)?\b|kỹ\s+sư\s+dữ\s+liệu|khai\s+thác\s+dữ\s+liệu"),
    ("AI/ML Engineer", r"\b(?:ai|ml|machine\s+learning|deep\s+learning|computer\s+vision|nlp|llm)\s+(?:engineer|researcher|scientist|specialist|talents?)\b|\bai\s+trainer\b"),
    ("Mobile", r"\b(?:mobile|ios|android|flutter|react\s+native)\s+(?:developer|engineer)\b|lập\s+trình\s+mobile"),
    ("Backend .NET", r"(?:^|(?<!\w))(?:\.net|c#|asp\.net|wpf)\s*(?:core\s+)?(?:backend\s+|full[\s\-]?stack\s+)?(?:developer|engineer|enginer)\b|(?:backend|software|full[\s\-]?stack|lập\s+trình\s+viên)\s*(?:server\s+)?(?:developer|engineer)?[^()\n]*(?:^|(?<!\w))(?:\.net|c#)\b"),
    ("Backend PHP", r"\b(?:php|laravel|magento|wordpress|drupal)\s+(?:full[\s\-]?stack\s+|backend\s+)?(?:developer|engineer)\b|(?:backend|software)\s+(?:developer|engineer)[^()\n]*\b(?:php|laravel)\b"),
    ("Backend Golang", r"\b(?:golang|go)\s+(?:backend\s+)?(?:developer|engineer)\b|(?:backend|software)\s+(?:developer|engineer)[^()\n]*\b(?:golang)\b"),
    ("Backend Node.js", r"\b(?:node(?:\.?js)?|nestjs)\s+(?:backend\s+)?(?:developer|engineer)\b"),
    ("Business Analyst", r"\b(?:business\s+analyst|ba|product\s+owner|product\s+manager|scrum\s+master|project\s+manager|bridge\s+system\s+engineer|brse)\b|phân\s+tích\s+nghiệp\s+vụ"),
    ("UI/UX Designer", r"\b(?:ui[\s/\-]?ux|product\s+designer|graphic\s+designer|ux\s+designer|ui\s+designer|fx\s+artist|technical\s+art)\b"),
    ("Embedded Engineer", r"\b(?:embedded|firmware|iot|semiconductor|fpga)\s+(?:ai\s+|software\s+|linux\s+|systems?\s+)?(?:engineer|developer|expert)\b|system\s+engineer\s*\([^)]*embedded|kỹ\s+sư\s+lập\s+trình\s+embedded"),
    ("Game Developer", r"\b(?:game|unity|unreal)\s+(?:developer|programmer|engineer)\b|lập\s+trình\s+game"),
    ("Security Engineer", r"\b(?:cyber\s*security|information\s+security|security|pentest|soc)\s+(?:solution\s+)?(?:engineer|specialist|analyst|manager)\b"),
    ("ERP/IS Specialist", r"\b(?:erp|sap|abap|is\s+specialist|dynamics)\b"),
)

GENERIC_DEV_TITLE = re.compile(
    r"\b(?:backend|back[\s\-]?end|software\s+(?:engineer|developer)|web\s+developer|full[\s\-]?stack\s+(?:developer|engineer)|lập\s+trình\s+viên|kỹ\s+sư\s+phần\s+mềm)\b",
    re.I,
)
TITLE_EXCLUSIONS = re.compile(
    r"\b(?:ai\s+engineer|ai\s+trainer|ai\s+developer|workflow\s+automation|itsm|machine\s+learning|data\s+scientist|data\s+engineer(?:ing)?|khai\s+thác\s+dữ\s+liệu|game|unity|cocos2d|embedded|firmware|iot|mobile|flutter|android|ios|ui[\s/\-]?ux|business\s+analyst|bridge\s+system\s+engineer|brse|sales|marketing|hr|accountant|helpdesk)\b",
    re.I,
)

# Canonical skill -> (regex pattern, is_stack_item).
# Word boundaries and negative lookaheads keep Java/JavaScript, React/React Native, C/C++/C#, Docker/Docker Compose, Git/GitHub/GitLab separate.
SKILL_PATTERNS = {
    "python": (r"(?<!\w)python(?!\w)", False),
    "frontend": (r"(?<!\w)front[\s\-]?end(?!\w)", False),
    "devops": (r"(?<!\w)devops(?!\w)", False),
    "kiểm thử": (r"(?<!\w)kiểm\s+thử(?!\w)", False),
    "django": (r"(?<!\w)django(?!\s+rest)(?!\w)", True),
    "django rest framework": (r"(?<!\w)(?:django\s+rest\s+framework|drf)(?!\w)", True),
    "fastapi": (r"(?<!\w)fastapi(?!\w)", True),
    "flask": (r"(?<!\w)flask(?!\w)", True),
    "odoo": (r"(?<!\w)odoo(?!\w)", True),
    "sqlalchemy": (r"(?<!\w)sqlalchemy(?!\w)", True),
    "celery": (r"(?<!\w)celery(?!\w)", True),
    "aiohttp": (r"(?<!\w)aiohttp(?!\w)", True),
    "starlette": (r"(?<!\w)starlette(?!\w)", True),
    "pydantic": (r"(?<!\w)pydantic(?!\w)", False),
    "pytest": (r"(?<!\w)pytest(?!\w)", True),
    "unittest": (r"(?<!\w)unittest(?!\w)", False),
    "java": (r"(?<!\w)java(?!\s*script)(?!\w)", False),
    "spring boot": (r"(?<!\w)spring\s+boot(?!\w)", True),
    "spring mvc": (r"(?<!\w)spring\s+mvc(?!\w)", True),
    "spring security": (r"(?<!\w)spring\s+security(?!\w)", True),
    "spring batch": (r"(?<!\w)spring\s+batch(?!\w)", True),
    "spring": (r"(?<!\w)spring(?!\s+(?:boot|mvc|security|batch))(?!\w)", True),
    "hibernate": (r"(?<!\w)hibernate(?!\w)", True),
    "jpa": (r"(?<!\w)jpa(?!\w)", False),
    "jdbc": (r"(?<!\w)jdbc(?!\w)", True),
    "quarkus": (r"(?<!\w)quarkus(?!\w)", True),
    "micronaut": (r"(?<!\w)micronaut(?!\w)", True),
    "jakarta ee": (r"(?<!\w)(?:jakarta\s+ee|j2ee)(?!\w)", True),
    "maven": (r"(?<!\w)maven(?!\w)", True),
    "gradle": (r"(?<!\w)gradle(?!\w)", True),
    "junit": (r"(?<!\w)junit(?!\w)", False),
    "mockito": (r"(?<!\w)mockito(?!\w)", False),
    "grpc": (r"(?<!\w)grpc(?!\w)", True),
    "protobuf": (r"(?<!\w)protobuf(?!\w)", True),
    "javascript": (r"(?<!\w)(?:javascript|ecmascript)(?!\w)", False),
    "typescript": (r"(?<!\w)typescript(?!\w)", True),
    "react": (r"(?<!\w)react(?:\.?js)?(?!\s+native)(?!\w)", True),
    "react native": (r"(?<!\w)react\s+native(?!\w)", True),
    "next.js": (r"(?<!\w)next\.?js(?!\w)", True),
    "vue": (r"(?<!\w)vue(?:\.?js)?(?!\w)", True),
    "angular": (r"(?<!\w)angular(?:\.?js|\s*\d+\+?)?(?!\w)", True),
    "svelte": (r"(?<!\w)svelte(?!\w)", True),
    "rxjs": (r"(?<!\w)rxjs(?!\w)", True),
    "pinia": (r"(?<!\w)pinia(?!\w)", False),
    "redux": (r"(?<!\w)redux(?!\w)", True),
    "html": (r"(?<!\w)html5?(?!\w)", False),
    "css": (r"(?<!\w)css3?(?!\w)", False),
    "sass": (r"(?<!\w)(?:sass|scss)(?!\w)", True),
    "tailwind": (r"(?<!\w)tailwind(?:\s*css)?(?!\w)", True),
    "webpack": (r"(?<!\w)webpack(?!\w)", False),
    "vite": (r"(?<!\w)vite(?!st)(?!\w)", False),
    "vitest": (r"(?<!\w)vitest(?!\w)", False),
    "playwright": (r"(?<!\w)playwright(?!\w)", True),
    "cypress": (r"(?<!\w)cypress(?!\w)", True),
    "selenium": (r"(?<!\w)selenium(?!\w)", True),
    "appium": (r"(?<!\w)appium(?!\w)", True),
    "robot framework": (r"(?<!\w)robot\s+framework(?!\w)", True),
    "postman": (r"(?<!\w)postman(?!\w)", True),
    "newman": (r"(?<!\w)newman(?!\w)", True),
    "jmeter": (r"(?<!\w)jmeter(?!\w)", True),
    "k6": (r"(?<!\w)k6(?!\w)", False),
    "jira": (r"(?<!\w)jira(?!\w)", True),
    "sql": (r"(?<!\w)sql(?!\s*alchemy|\s*lite)(?!\w)", False),
    "postgresql": (r"(?<!\w)(?:postgresql|postgres)(?!\w)", True),
    "mysql": (r"(?<!\w)mysql(?!\w)", True),
    "sqlite": (r"(?<!\w)sqlite(?!\w)", True),
    "mongodb": (r"(?<!\w)mongodb(?!\w)", True),
    "oracle": (r"(?<!\w)oracle(?!\w)", True),
    "redis": (r"(?<!\w)redis(?!\w)", True),
    "elasticsearch": (r"(?<!\w)(?:elasticsearch|elastic\s+search)(?!\w)", True),
    "kafka": (r"(?<!\w)kafka(?!\w)", True),
    "rabbitmq": (r"(?<!\w)rabbitmq(?!\w)", True),
    "linux": (r"(?<!\w)(?:linux|ubuntu|centos|red\s*hat)(?!\w)", False),
    "bash": (r"(?<!\w)(?:bash|shell\s+script(?:ing)?)(?!\w)", False),
    "docker": (r"(?<!\w)docker(?!\s+compose)(?!\w)", True),
    "docker compose": (r"(?<!\w)docker[\s\-]+compose(?!\w)", True),
    "kubernetes": (r"(?<!\w)(?:kubernetes|k8s|eks|aks|gke)(?!\w)", True),
    "helm": (r"(?<!\w)helm(?!\w)", True),
    "terraform": (r"(?<!\w)terraform(?!\w)", True),
    "ansible": (r"(?<!\w)ansible(?!\w)", True),
    "jenkins": (r"(?<!\w)jenkins(?!\w)", True),
    "gitlab ci": (r"(?<!\w)gitlab[\s\-]*(?:ci(?:/cd)?)(?!\w)", True),
    "github actions": (r"(?<!\w)github\s+actions(?!\w)", True),
    "aws": (r"(?<!\w)(?:aws|amazon\s+web\s+services)(?!\w)", True),
    "azure": (r"(?<!\w)azure(?!\w)", True),
    "google cloud": (r"(?<!\w)(?:google\s+cloud|gcp)(?!\w)", True),
    "prometheus": (r"(?<!\w)prometheus(?!\w)", True),
    "grafana": (r"(?<!\w)grafana(?!\w)", True),
    "nginx": (r"(?<!\w)nginx(?!\w)", False),
    "git": (r"(?<!\w)git(?!\s*(?:hub|lab))(?!\w)", False),
    "openapi": (r"(?<!\w)(?:openapi|swagger)(?!\w)", False),
    "json": (r"(?<!\w)json(?!\w)", False),
    "excel": (r"(?<!\w)excel(?!\w)", False),
    "power bi": (r"(?<!\w)power\s*bi(?!\w)", True),
    "tableau": (r"(?<!\w)tableau(?!\w)", True),
    "c#": (r"(?<!\w)c#(?![\w+#])", True),
    "c++": (r"(?<!\w)c\+\+(?![\w+#])", True),
    ".net": (r"(?<!\w)\.net(?:\s+core)?(?!\w)", True),
    "golang": (r"(?<!\w)golang(?!\w)", True),
    "php": (r"(?<!\w)php(?!\w)", True),
    "laravel": (r"(?<!\w)laravel(?!\w)", True),
    "node.js": (r"(?<!\w)node\.?js(?!\w)", True),
}

ROLE_DEFAULT_SCOPE = {
    "Backend Python": "backend python",
    "Backend Java": "backend java",
    "Frontend": "frontend",
    "DevOps/Cloud": "devops",
    "QA/Testing": "kiểm thử phần mềm",
    "Data Analyst": "data analysis",
}

ROLE_ALIAS_SCOPES = {
    "Backend Python": ("backend python", "python backend"),
    "Backend Java": ("backend java", "java backend"),
    "Frontend": ("frontend",),
    "DevOps/Cloud": ("devops",),
    "QA/Testing": ("kiểm thử phần mềm", "software testing"),
    "Data Analyst": ("data analysis",),
}

INTERNSHIP_COMMITMENT_CUE = re.compile(
    r"\b(?:of\s+internship|internship\s+duration|internship\s+period|thực\s+tập\s+(?:trong\s+)?\d|thời\s+gian\s+thực\s+tập|kéo\s+dài\s+\d+\s*(?:tháng|months?)|working\s+days?\s+per\s+week)\b",
    re.I,
)
NON_EXPERIENCE_LINE_CUE = re.compile(
    r"\b(?:tuổi\s+từ|độ\s+tuổi|age\s*[:\-]?\s*\d{2}|bảo\s+hành|thành\s+lập\s+hơn|lương\s+tháng\s+13|probation|thử\s+việc\s+\d)\b",
    re.I,
)
EXPERIENCE_CONTEXT_CUE = re.compile(
    r"\b(?:kinh\s+nghiệm|experience|experiences|exp|làm\s+việc|working|work\s+related|phát\s+triển|developing|development|lập\s+trình|kiểm\s+thử|testing|vị\s+trí|position|role|industry)\b",
    re.I,
)
YEAR_REQUIREMENT_PATTERN = re.compile(
    r"(?:(?P<strict>trên|hơn|over|more\s+than|greater\s+than)\s+|(?P<min>tối\s+thiểu|ít\s+nhất|at\s+least|minimum|min|từ|from)\s+)?"
    r"(?P<num>\d{1,2}(?:[.,]\d+)?)(?:\s*[-–~]\s*\d{1,2}(?:[.,]\d+)?|\s+to\s+\d{1,2})?\s*(?P<plus>\+)?\s*(?:năm|years?|yrs?)(?:\s*\+)?\b",
    re.I,
)
MONTH_REQUIREMENT_PATTERN = re.compile(
    r"(?:(?P<strict>trên|hơn|over|more\s+than)\s+|(?P<min>tối\s+thiểu|ít\s+nhất|at\s+least|minimum|từ|from)\s+)?"
    r"(?P<num>\d{1,2})(?:\s*[-–~]\s*\d{1,2})?\s*(?P<plus>\+)?\s*(?:tháng|months?)\b",
    re.I,
)


def _span(field, text, match, **extra):
    quote = text[match.start():match.end()]
    require(quote == match.group(0), "Evidence span offset mismatch")
    return dict(field=field, start=match.start(), end=match.end(), quote=quote, **extra)


def _clean_field(row, field):
    text = row.get(field, "") or ""
    if ERROR_CELL.search(text) or "\ufffd" in text:
        return ""
    return text


def extract_role(row):
    title = _clean_field(row, "title_for_matching")
    matches = []
    if title:
        for role, pattern in TITLE_ROLE_PATTERNS:
            if role in {"Backend Python", "Backend Java"} and TITLE_EXCLUSIONS.search(title):
                continue
            m = re.search(pattern, title, re.I)
            if m:
                matches.append((role, _span("title_for_matching", title, m, role=role, source="title_cue")))
        if len(matches) > 1 and not re.search(r"\b(?:backend|back[\s\-]?end|full[\s\-]?stack)\b", title, re.I):
            non_backend = [item for item in matches if item[0] in {"Data Analyst", "QA/Testing", "DevOps/Cloud"}]
            if len(non_backend) == 1:
                matches = non_backend
        if len(matches) == 1:
            return matches[0][0], [matches[0][1]], [matches[0][0]]
        if len(matches) > 1:
            return "", [ev for _, ev in matches], [r for r, _ in matches]
        for role, pattern in OTHER_TITLE_ROLES:
            m = re.search(pattern, title, re.I)
            if m:
                matches.append((role, _span("title_for_matching", title, m, role=role, source="other_title_cue")))
        if len(matches) == 1:
            return matches[0][0], [matches[0][1]], [matches[0][0]]
        if len(matches) > 1:
            return "", [ev for _, ev in matches], [r for r, _ in matches]

    # Secondary check: generic developer/engineer title with unambiguous single-stack section evidence.
    if title and GENERIC_DEV_TITLE.search(title) and not TITLE_EXCLUSIONS.search(title):
        req_text = _clean_field(row, "requirements_text")
        task_text = _clean_field(row, "tasks_text")
        section_candidates = []
        body_rules = (
            ("Backend Python", r"(?<!\w)(?:django|fastapi|flask|odoo)(?!\w)"),
            ("Backend Java", r"(?<!\w)(?:spring\s+boot|spring\s+mvc|hibernate|quarkus|jakarta\s+ee|j2ee)(?!\w)"),
            ("Frontend", r"(?<!\w)(?:react(?:\.?js)?(?!\s+native)|vue(?:\.?js)?|angular|next\.?js)(?!\w)"),
        )
        for role, pattern in body_rules:
            if role == "Frontend" and re.search(r"\bback[\s\-]?end\b", title, re.I) and not re.search(r"\b(?:front[\s\-]?end|full[\s\-]?stack)\b", title, re.I):
                continue
            for field, content in (("requirements_text", req_text), ("tasks_text", task_text)):
                m = re.search(pattern, content, re.I)
                if m:
                    section_candidates.append((role, _span(field, content, m, role=role, source="body_framework_cue")))
                    break
        if len(section_candidates) == 1:
            return section_candidates[0][0], [section_candidates[0][1]], [section_candidates[0][0]]
        if len(section_candidates) > 1:
            return "", [ev for _, ev in section_candidates], [r for r, _ in section_candidates]
    return "", [], []


def extract_skills_and_stack(row):
    core_skills, core_stack, preferred_skills = {}, {}, {}
    for field in CORE_FIELDS:
        text = _clean_field(row, field)
        if not text:
            continue
        for skill, (pattern, is_stack) in SKILL_PATTERNS.items():
            if skill in core_skills:
                continue
            m = re.search(pattern, text, re.I)
            if m:
                line_start = text.rfind("\n", 0, m.start()) + 1
                line_end = text.find("\n", m.end())
                sentence = text[line_start:line_end if line_end >= 0 else len(text)]
                if re.search(r"không\s+bắt\s+buộc|not\s+required|optional|ưu\s+tiên|preferred|nice\s+to\s+have", sentence, re.I):
                    preferred_skills[skill] = _span(field, text, m, skill=skill, section_type="optional_or_preferred")
                    continue
                span = _span(field, text, m, skill=skill, section_type="core")
                core_skills[skill] = span
                if is_stack:
                    core_stack[skill] = span
    pref_text = _clean_field(row, "preferred_requirements_text")
    if pref_text:
        for skill, (pattern, _) in SKILL_PATTERNS.items():
            if skill in core_skills or skill in preferred_skills:
                continue
            m = re.search(pattern, pref_text, re.I)
            if m:
                preferred_skills[skill] = _span("preferred_requirements_text", pref_text, m, skill=skill, section_type="preferred")
    return sorted(core_skills), sorted(core_stack), core_skills, core_stack, preferred_skills


def _infer_line_scopes(line, role):
    # Preserve explicit role/technology scopes. A Python mention is not evidence
    # of backend duration; a role title does not assign every tool its months.
    from .experience_rules import explicit_scopes
    return explicit_scopes(line)


def extract_experience(row, role=""):
    req_text = _clean_field(row, "requirements_text")
    if not req_text:
        return {}, []
    scoped_months = {}
    evidence_items = []
    offset = 0
    for line in req_text.splitlines(keepends=True):
        stripped = line.strip()
        line_start = offset
        offset += len(line)
        if not stripped:
            continue
        if INTERNSHIP_COMMITMENT_CUE.search(stripped) or NON_EXPERIENCE_LINE_CUE.search(stripped):
            continue
        if not EXPERIENCE_CONTEXT_CUE.search(stripped):
            continue
        from .experience_rules import excludes_minimum
        if excludes_minimum(stripped):
            continue
        # Multiple bounds in one line require clause-level analysis not supplied
        # by this extractor; leave unknown rather than attach every number to every skill.
        if len(list(YEAR_REQUIREMENT_PATTERN.finditer(line))) + len(list(MONTH_REQUIREMENT_PATTERN.finditer(line))) > 1:
            continue
        found_in_line = False
        for m in YEAR_REQUIREMENT_PATTERN.finditer(line):
            raw_num = float(m.group("num").replace(",", "."))
            if raw_num <= 0 or raw_num > 20:
                continue
            months = int(round(raw_num * 12))
            if months <= 0:
                continue
            strict = bool(m.group("strict"))
            # Determine scope from the clause surrounding the match first, then the full line.
            clause_start = max(0, m.start() - 40)
            clause_end = min(len(line), m.end() + 90)
            scopes = _infer_line_scopes(line[clause_start:clause_end], role) or _infer_line_scopes(line, role)
            quote = req_text[line_start + line.find(stripped):line_start + line.find(stripped) + len(stripped)]
            q_start = line_start + line.find(stripped)
            q_end = q_start + len(stripped)
            require(req_text[q_start:q_end] == quote, "Experience line quote offset mismatch")
            for scope in scopes:
                scoped_months[scope] = max(scoped_months.get(scope, 0), months)
            evidence_items.append(dict(
                field="requirements_text",
                start=q_start,
                end=q_end,
                quote=quote,
                match_text=m.group(0),
                threshold_months=months,
                strictly_greater=strict,
                scopes=scopes,
            ))
            found_in_line = True
        if not found_in_line:
            for m in MONTH_REQUIREMENT_PATTERN.finditer(line):
                months = int(m.group("num"))
                if months <= 0 or months > 120:
                    continue
                strict = bool(m.group("strict"))
                scopes = _infer_line_scopes(line, role)
                q_start = line_start + line.find(stripped)
                q_end = q_start + len(stripped)
                quote = req_text[q_start:q_end]
                require(req_text[q_start:q_end] == quote, "Experience month quote offset mismatch")
                for scope in scopes:
                    scoped_months[scope] = max(scoped_months.get(scope, 0), months)
                evidence_items.append(dict(
                    field="requirements_text",
                    start=q_start,
                    end=q_end,
                    quote=quote,
                    match_text=m.group(0),
                    threshold_months=months,
                    strictly_greater=strict,
                    scopes=scopes,
                ))
    return scoped_months, evidence_items


def extract_jd_row(row):
    from .requirements_logic import requirement_logic
    role, role_evidence, role_candidates = extract_role(row)
    skills, stack, skill_evidence, stack_evidence, preferred_evidence = extract_skills_and_stack(row)
    experience, experience_evidence = extract_experience(row, role)
    for item in [*role_evidence, *skill_evidence.values(), *stack_evidence.values(), *preferred_evidence.values(), *experience_evidence]:
        field_text = row[item["field"]]
        require(field_text[item["start"]:item["end"]] == item["quote"], f"Literal evidence check failed on {row.get('job_id')}/{item['field']}")
    receipt = dict(
        job_id=row["job_id"],
        extractor_version=EXTRACTOR_VERSION,
        role=role,
        role_candidates=role_candidates,
        role_evidence=role_evidence,
        skills=skills,
        stack=stack,
        skill_evidence=skill_evidence,
        stack_evidence=stack_evidence,
        preferred_skills=sorted(preferred_evidence),
        preferred_skill_evidence=preferred_evidence,
        experience=experience,
        experience_evidence=experience_evidence,
        requirement_clauses=requirement_logic(row, SKILL_PATTERNS),
        unknown_fields=[name for name, val in (("role", role), ("skills", skills), ("stack", stack), ("experience", experience)) if not val],
    )
    return receipt


def evaluate_pilot_extraction():
    _, pilot_rows = csv_rows(ROOT / "jobapply_pilot_v1/jobs_pilot.csv")
    _, exp_rows = csv_rows(ROOT / "jobapply_pilot_v1/jobapply_experience_v2/jd_experience.csv")
    pilot_by_id = {r["job_id"]: r for r in pilot_rows}
    reference_by_id = {}
    for row in exp_rows:
        jid = row["job_id"]
        reference_by_id.setdefault(jid, []).append(row)

    role_map = {
        "Backend Python": "Backend Python",
        "Backend Java": "Backend Java",
        "Frontend": "Frontend",
        "DevOps / Cloud": "DevOps/Cloud",
        "QA / Testing": "QA/Testing",
        "Data Analyst": "Data Analyst",
    }
    role_correct = 0
    exp_presence_tp = exp_presence_fp = exp_presence_fn = exp_unknown_tn = 0
    exp_exact_max_matches = 0
    exp_total_with_threshold = 0
    details = []

    for jid, row in sorted(pilot_by_id.items()):
        extracted = extract_jd_row(row)
        expected_role = role_map[row["pilot_group"]]
        if extracted["role"] == expected_role:
            role_correct += 1
        reference_entries = [g for g in reference_by_id.get(jid, []) if g["threshold_months"].strip()]
        reference_max = max((int(g["threshold_months"]) for g in reference_entries), default=None)
        pred_max = max(extracted["experience"].values(), default=None)
        if reference_max is not None:
            exp_total_with_threshold += 1
            if pred_max is not None:
                exp_presence_tp += 1
                if pred_max == reference_max:
                    exp_exact_max_matches += 1
            else:
                exp_presence_fn += 1
        else:
            if pred_max is None:
                exp_unknown_tn += 1
            else:
                exp_presence_fp += 1
        details.append(dict(
            job_id=jid,
            expected_role=expected_role,
            extracted_role=extracted["role"],
            reference_threshold_months=[int(g["threshold_months"]) for g in reference_entries],
            extracted_experience=extracted["experience"],
            skills_count=len(extracted["skills"]),
            stack_count=len(extracted["stack"]),
        ))

    precision = exp_presence_tp / (exp_presence_tp + exp_presence_fp) if (exp_presence_tp + exp_presence_fp) else 0.0
    recall = exp_presence_tp / (exp_presence_tp + exp_presence_fn) if (exp_presence_tp + exp_presence_fn) else 0.0
    return dict(
        extractor_version=EXTRACTOR_VERSION,
        evaluation_scope="50 protected pilot JDs (development only; never used as test)",
        pilot_jd_count=len(pilot_by_id),
        role_accuracy=round(role_correct / len(pilot_by_id), 4),
        role_correct=role_correct,
        experience_detection=dict(
            tp=exp_presence_tp,
            fp=exp_presence_fp,
            fn=exp_presence_fn,
            unknown_preserved_tn=exp_unknown_tn,
            precision=round(precision, 4),
            recall=round(recall, 4),
            max_threshold_value_match_count=exp_exact_max_matches,
            comparison_note="Development internal annotations; presence and max-value agreement do not establish scoped extraction accuracy",
            max_threshold_value_match_rate=round(exp_exact_max_matches / exp_total_with_threshold, 4) if exp_total_with_threshold else 0.0,
        ),
        details=details,
    )


def enrich_upstream_jds(upstream_run, output):
    upstream_run = Path(upstream_run).resolve()
    from .common import verify
    verify(upstream_run, "upstream")
    verify(upstream_run / "dataset", "dataset")
    cols, canonical = csv_rows(upstream_run / "canonical_jd.csv")
    records = {r["external_id"]: r for r in read_lines(upstream_run / "dataset/records.jsonl")}

    enriched_rows = []
    evidence_rows = []
    prospective_keep_stats = Counter()
    prospective_role_counts = Counter()

    for row in canonical:
        jid = row["job_id"]
        receipt = extract_jd_row(row)
        evidence_rows.append(receipt)
        new_row = dict(
            **row,
            extracted_role=receipt["role"],
            extracted_skills=";".join(receipt["skills"]),
            extracted_stack=";".join(receipt["stack"]),
            extracted_experience_json=json.dumps(receipt["experience"], ensure_ascii=False, sort_keys=True),
            extractor_version=EXTRACTOR_VERSION,
        )
        enriched_rows.append(new_row)
        rec = records[jid]
        if rec["decision"] == "keep" and not rec["development_only"]:
            prospective_keep_stats["total"] += 1
            for field in ("role", "skills", "stack", "experience"):
                if receipt[field]:
                    prospective_keep_stats[f"with_{field}"] += 1
                else:
                    prospective_keep_stats[f"missing_{field}"] += 1
            prospective_role_counts[receipt["role"] or "unknown"] += 1

    pilot_eval = evaluate_pilot_extraction()
    folder = fresh_folder(output, (upstream_run,))
    out_cols = [*cols, "extracted_role", "extracted_skills", "extracted_stack", "extracted_experience_json", "extractor_version"]
    write_csv(folder / "canonical_jd_enriched.csv", enriched_rows, out_cols)
    write_json(folder / "jd_extraction_evidence.json", evidence_rows)
    write_json(folder / "pilot_extraction_eval.json", pilot_eval)
    summary = dict(
        extractor_version=EXTRACTOR_VERSION,
        upstream_manifest_sha256=file_hash(upstream_run / "manifest.json"),
        total_jds=len(enriched_rows),
        prospective_keep_coverage=dict(prospective_keep_stats),
        prospective_keep_roles=dict(prospective_role_counts),
        pilot_evaluation={k: v for k, v in pilot_eval.items() if k != "details"},
        note="Rule-based literal extraction with character offsets; unknown fields remain empty/{} and are never filled with zero.",
    )
    write_json(folder / "summary.json", summary)
    seal(folder, "jd-extraction", dict(extractor_version=EXTRACTOR_VERSION, upstream_manifest_sha256=summary["upstream_manifest_sha256"]))
    return summary
