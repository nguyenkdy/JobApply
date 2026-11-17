"""Versioned technical clauses/tasks, with explicit evidence and abstention.

Only known-JD development text and independent test fixtures inform this policy.
Closed grammar rejects unconsumed prose and ambiguous connective scope.
"""
from copy import deepcopy
from decimal import Decimal
import re

from .common import require
from .expanded_labels import source_field
from .extraction import SKILL_PATTERNS
from .refinement import EXTRA_SKILLS

VERSION = "expanded-technical-proxy-v2"
POLICY = dict(version=VERSION, labels="automatic_rule_proxy", negative="Explicit mandatory contradiction only; missing skill/role difference is never negative",
    partial="Shared affirmative technology plus same occupation or shared explicit task function; title inequality alone is unresolved",
    strong="Same specific occupation, all parsed mandatory technology and scoped duration satisfied, no unresolved technical/duration conditions",
    time="Exact scope; employment/contract only; no total-to-technology conversion. Range minimum is retained with unresolved upper interpretation",
    scope="Bounded technical compatibility, not verified hiring suitability; education/languages/soft skills outside target",
    exposure="All 120 CV groups become development in a separate overlay because revision follows their v1 diagnostic results; original partitions preserved only for comparison",
    holdout_eligible=False, gold=False, model_training=False)

ALIASES = {"postgres": "postgresql", "nodejs": "node.js", "reactjs": "react", "react.js": "react",
           "vuejs": "vue", "vue.js": "vue", "nextjs": "next.js", "nestjs": "nestjs",
           "java script": "javascript", "ecmascript": "javascript", "k8s": "kubernetes",
           "dotnet": ".net", "dot net": ".net", "asp.net core": "asp.net core"}
PATTERNS = {k: v[0] for k, v in {**SKILL_PATTERNS, **EXTRA_SKILLS}.items()}
for _name in ("asp.net core", ".net", "h2", "xunit", "duckdb", "room", "gitHub actions"):
    PATTERNS[_name.casefold()] = r"(?<!\w)" + re.escape(_name) + r"(?!\w)"
for _alias, _canonical in ALIASES.items():
    PATTERNS[_canonical] = "(?:" + PATTERNS.get(_canonical, re.escape(_canonical)) + "|(?<!\\w)" + re.escape(_alias) + "(?!\\w))"

OPTIONAL = re.compile(r"ưu\s+tiên|không\s+bắt\s+buộc|không\s+yêu\s+cầu|không\s+cần|lợi\s+thế|preferred|optional|nice[ -]to[ -]have|not\s+required|advantage|no\s+(?:prior\s+)?experience", re.I)
CONDITION = re.compile(r"\b(?:nếu|if|unless|depending|tùy|tuỳ)\b|ứng viên.*(?:hoặc|either)|for\s+(?:junior|senior|lead)|(?:junior|senior|lead)\s*[:：]", re.I)
LEVEL = re.compile(r"\b(?:junior|senior|fresher|lead)\b", re.I)
NEGATIVE = re.compile(r"\b(?:chưa|không|not|without|never)\b", re.I)
NUMERIC_TIME = re.compile(r"\d+(?:[.,]\d+)?\s*(?:\+|[-–]\s*\d+)?\s*(?:năm|tháng|years?|months?)\b", re.I)
PREFIX = re.compile(r"^(?:(?:có\s+)?(?:kinh nghiệm|kiến thức|hiểu biết)(?:\s+(?:làm việc|vững chắc|vững|sâu|tốt|thực tế))?(?:\s+(?:về|với|trong|sử dụng|lập trình))?|"
    r"(?:sử dụng\s+)?thành thạo|bắt buộc(?:\s+(?:phải|có|sử dụng))*|yêu cầu|"
    r"(?:must\s+(?:have|know)\s+)?(?:(?:hands[ -]on|solid|strong|good|working|proven)\s+)?(?:experience|knowledge|understanding|proficiency)(?:\s+(?:of|in|with|using))?|"
    r"proficient\s+(?:in|with)|must\s+know|required(?:\s+skills)?)[\s:：]+", re.I)

TASKS = {
    "backend_services": r"(?:viết|xây dựng|phát triển|thiết kế|build|develop|implement|design)[^.\n;]{0,70}\b(?:api|back[ -]?end|microservices?|server[ -]side)\b",
    "user_interface": r"(?:viết|xây|sửa|dựng|phát triển|thiết kế|build|develop|implement|design)[^.\n;]{0,65}(?:giao diện|\bui\b|front[ -]?end|web pages?)",
    "quality_testing": r"kiểm thử|test cases?|test plans?|automation testing|automated tests?|manual testing|thử api|kiểm (?:chức năng|api)|tái hiện lỗi",
    "data_pipeline": r"\betl\b|data pipelines?|luồng (?:nạp|xử lý|hợp nhất)|(?:nạp|hợp nhất|chuẩn hóa)[^.\n;]{0,35}(?:dữ liệu|danh mục)|kho dữ liệu|data warehouse",
    "ml_modeling": r"huấn luyện|\btrain(?:ing)?\b[^.\n;]{0,30}\bmodel|(?:phân loại|dự báo|nhận dạng)[^.\n;]{0,40}(?:ảnh|mô hình|baseline)|machine learning models?",
    "infrastructure_operations": r"(?:cấu hình|quản trị|vận hành|triển khai|configure|operate|deploy)[^.\n;]{0,55}(?:linux|container|kubernetes|hạ tầng|máy chủ|infrastructure|servers?)|\bci/cd\b|khôi phục cấu hình",
    "mobile_application": r"(?:viết|làm|phát triển|build|develop)[^.\n;]{0,55}(?:ứng dụng[^.\n;]{0,25}(?:điện thoại|android|ios)|mobile app|android app|ios app)",
    "database_design": r"(?:thiết kế|tối ưu|design|optimi[sz]e)[^.\n;]{0,45}(?:cơ sở dữ liệu|database|sql queries)|schema migration",
}


def canon(term):
    value = re.sub(r"\s+", " ", term.casefold()).strip()
    return ALIASES.get(value, value)


def spans(text, field):
    """Keep original offsets, separate true line/semicolon boundaries only."""
    for m in re.finditer(r"[^\n;]+", text):
        if m[0].strip():
            yield dict(field=field, start=m.start(), end=m.end(), quote=m[0])


def clean(text):
    return re.sub(r"\s+", " ", text).strip().lstrip("-•* ").rstrip(". ")


def mentions(text):
    hits = [(m.start(), m.end(), key, m[0]) for key, pat in PATTERNS.items() for m in re.finditer(pat, text, re.I)]
    chosen = []
    # A framework/language with a longer name must not also imply its substring.
    for start, end, key, quote in sorted(hits, key=lambda h: (-(h[1]-h[0]), h[0], h[2])):
        if not any(start < b and a < end for a, b, _, _ in chosen):
            chosen.append((start, end, key, quote))
    return sorted(chosen)


def logic_tree(text):
    """Parse complete technology-only expressions, preserving parentheses.

    Mixed AND/OR at one level and plain comma/slash lists remain unresolved.
    Comma + explicit final AND is accepted as one conjunction.
    """
    hits = mentions(text)
    if not hits:
        return None
    transformed, cursor, terms = [], 0, []
    for index, (start, end, term, _) in enumerate(hits):
        transformed += [text[cursor:start], f"T{index}"]
        terms.append(term)
        cursor = end
    transformed.append(text[cursor:])
    expr = "".join(transformed)
    expr = re.sub(r"\b(?:và|and)\b|&", " AND ", expr, flags=re.I)
    expr = re.sub(r"\b(?:hoặc|or)\b", " OR ", expr, flags=re.I)
    # A tokenization with punctuation adjacent to T is handled independently.
    tokens = re.findall(r"T\d+|AND|OR|[(),]|[^\s(),]+", expr)
    position = 0
    def level():
        nonlocal position
        nodes, operators = [], []
        expect_node = True
        while position < len(tokens) and tokens[position] != ")":
            token = tokens[position]
            position += 1
            if expect_node:
                if token == "(":
                    node = level()
                    if node is None or position >= len(tokens) or tokens[position] != ")":
                        return None
                    position += 1
                elif re.fullmatch(r"T\d+", token):
                    node = dict(op="term", term=terms[int(token[1:])])
                else:
                    return None
                nodes.append(node)
                expect_node = False
            elif token in {"AND", "OR", ","}:
                operators.append(token)
                expect_node = True
            else:
                return None
        if expect_node or not nodes:
            return None
        kinds = set(operators)
        if "," in kinds:
            if "AND" not in kinds or "OR" in kinds:
                return None
            kinds.discard(",")
        if len(kinds) > 1:
            return None
        return nodes[0] if len(nodes) == 1 else dict(op="any" if kinds == {"OR"} else "all", children=nodes)
    tree = level()
    return tree if position == len(tokens) else None


def tree_state(tree, positive, negative):
    if tree["op"] == "term":
        return "yes" if tree["term"] in positive else "no" if tree["term"] in negative else "unknown"
    states = [tree_state(c, positive, negative) for c in tree["children"]]
    if tree["op"] == "any":
        return "yes" if "yes" in states else "no" if all(s == "no" for s in states) else "unknown"
    return "no" if "no" in states else "yes" if all(s == "yes" for s in states) else "unknown"


def optional_state(text):
    m = OPTIONAL.search(text)
    if not m:
        return None
    prefix = clean(text[:m.start()]).casefold()
    # A sentence mixing an explicit requirement and preference is not wholly optional.
    if PREFIX.match(prefix) or re.search(r"\bmust\b|bắt buộc", prefix):
        return "mixed_unresolved"
    return "preferred"


SCOPE_WORDS = {
    "professional experience": r"(?:professional |working )?experience|kinh nghiệm(?: (?:làm việc|nghề nghiệp))?",
    "software development": r"(?:kinh nghiệm )?(?:lập trình|phát triển phần mềm)|(?:experience (?:in|as) )?(?:software (?:development|engineering|engineer)|developers?)",
    "kiểm thử phần mềm": r"(?:kinh nghiệm (?:trong |về )?)?(?:kiểm thử(?: phần mềm)?|qa|automation testing)|(?:experience (?:in|with) )?(?:software testing|qa|automation testing)",
    "backend": r"(?:kinh nghiệm (?:lập trình |phát triển )?)?back[ -]?end|(?:experience in )?back[ -]?end development",
    "frontend": r"(?:kinh nghiệm (?:lập trình |phát triển )?)?front[ -]?end|(?:experience in )?front[ -]?end development",
    "devops": r"(?:kinh nghiệm (?:về |với )?|experience (?:in|with) )?devops",
}


def parse_duration(text):
    value = clean(text).casefold()
    if optional_state(value) or CONDITION.search(value) or re.search(r"tối đa|at most|up to|less than|dưới\s*\d|không|\bno\b|\bnot\b|~", value):
        return None
    number = r"\d+(?:[.,]\d+)?"
    pattern = (r"(?:có\s+|yêu cầu\s+|kinh nghiệm\s+)?(?P<bound>tối thiểu|ít nhất|từ|trên|at least|minimum(?: of)?|more than|over)?\s*"
               r"(?P<low>"+number+r")(?:\s*(?:[-–]|đến|to)\s*(?P<high>"+number+r"))?\s*(?P<plus>\+)?\s*"
               r"(?P<unit>năm|tháng|years?|months?)(?:\s+trở lên)?\s+(?:of\s+)?(?P<scope>.+?)(?:\s+trở lên)?")
    m = re.fullmatch(pattern, value)
    if not m:
        return None
    factor = 12 if m["unit"] in {"năm", "year", "years"} else 1
    low = Decimal(m["low"].replace(",", "."))*factor
    high = Decimal(m["high"].replace(",", "."))*factor if m["high"] else None
    if low <= 0 or low != int(low) or (high is not None and (high < low or high != int(high))):
        return None
    scope_text = m["scope"].strip().rstrip(".")
    scope = next((key for key, pat in SCOPE_WORDS.items() if re.fullmatch(pat, scope_text, re.I)), None)
    if scope is None:
        prefix = re.sub(r"^(?:kinh nghiệm(?: làm việc)?(?: (?:lập trình|phát triển|sử dụng|về|với|trong))*|experience(?: (?:in|with|using|developing))?|working (?:with|in))\s+", "", scope_text)
        hits = mentions(prefix)
        if len(hits) == 1 and hits[0][0] == 0 and hits[0][1] == len(prefix):
            scope = hits[0][2]
    if scope is None:
        return None
    return dict(scope=scope, months=int(low), strict=m["bound"] in {"trên", "more than", "over"},
                range_upper_months=int(high) if high is not None else None,
                upper_interpretation_unresolved=high is not None, normalization="explicit-duration-scope-v2")


def parse_technical(text, field="requirements_text", context="required"):
    quote = clean(text)
    terms = sorted({h[2] for h in mentions(quote)})
    base = dict(terms=terms, tree=None, duration=None)
    optional = optional_state(quote)
    if context == "conditional" or CONDITION.search(quote):
        return dict(base, state="unresolved", reason="conditional_applicability")
    if field == "preferred_requirements_text" or context == "preferred":
        return dict(base, state="preferred", reason="preferred_section")
    if optional:
        return dict(base, state="preferred" if optional == "preferred" else "unresolved", reason=optional)
    duration = parse_duration(quote)
    if duration:
        return dict(base, state="duration", reason="explicit_scoped_duration") | {"duration": duration}
    if NUMERIC_TIME.search(quote):
        return dict(base, state="unresolved", reason="duration_syntax_or_scope")
    prefix = PREFIX.match(quote)
    if prefix:
        body = quote[prefix.end():].strip()
        # Explicit 'one of' determines alternatives, including comma lists.
        one_of = re.match(r"(?:một trong(?: các)?|(?:at least )?one of(?: the following)?)\s*:?[ ]*", body, re.I)
        if one_of:
            body = body[one_of.end():]
            body = re.sub(r"\s*[,/]\s*", " OR ", body)
        tree = logic_tree(body)
        if tree:
            return dict(base, tree=tree, state="mandatory", reason="complete_explicit_technical_requirement")
    return dict(base, state="unresolved" if terms or prefix else "outside_technical_grammar", reason="unconsumed_requirement_prose")


def functions(text, field):
    result = {}
    # Ignore the CV's first role heading by passing only its body from caller.
    for m in re.finditer(r"[^\n;!?]+?(?:\.(?=\s|$)|$|(?=[\n;!?]))", text):
        segment = m[0]
        if NEGATIVE.search(segment) or OPTIONAL.search(segment):
            continue
        for family, pattern in TASKS.items():
            if re.search(pattern, segment, re.I):
                result.setdefault(family, []).append(dict(field=field, start=m.start(), end=m.end(), quote=segment))
    return result


def role_overlay(record):
    """Preserve specific prior occupations; only add explicit occupational title cues."""
    role = record["role"]
    title = source_field(record, "title_for_matching")
    evidence = []
    patterns = {
        "application operations": r"\bapplication operator\b",
        "integration engineer": r"\bapi integration engineer\b|k[ĩỹ] sư tích hợp",
        "education/training": r"\bcurriculum developer\b",
        "ui/ux designer": r"\bux/ui design(?:er)?\b",
        "backend (unspecified stack)": r"\bback[ -]?end (?:developer|engineer)\b|\bmicroservices? developer\b",
    }
    if not role or record.get("role_precision") == "generic":
        for key, pattern in patterns.items():
            for m in re.finditer(pattern, title, re.I):
                evidence.append(dict(role=key, field="title_for_matching", start=m.start(), end=m.end(), quote=m[0]))
        candidates = {e["role"] for e in evidence}
        if len(candidates) == 1:
            role = next(iter(candidates))
    return dict(role=role, previous_role=record["role"], evidence=evidence,
                specific=bool(role) and "unspecified" not in role and record.get("role_precision") != "generic")


def jd_facts(record):
    title = role_overlay(record)
    clauses, positive, excluded = [], {}, []
    preferred_spans = set()
    for field in ("requirements_text", "preferred_requirements_text"):
        text = source_field(record, field)
        levels = set(LEVEL.findall(text.casefold()))
        conditional_document = len(levels) > 1
        context = "conditional" if conditional_document else "preferred" if field.startswith("preferred") else "required"
        for span in spans(text, field):
            heading = clean(span["quote"]).casefold().rstrip(":：")
            if heading in {"nice to have", "preferred", "ưu tiên", "điểm cộng"}:
                context = "preferred"
                continue
            if heading in {"requirements", "required", "must have", "yêu cầu", "bắt buộc"} and not conditional_document:
                context = "required"
                continue
            if LEVEL.search(heading) and span["quote"].strip().endswith((":", "：")):
                context = "conditional"
                continue
            if re.search(r"\b(?:either|one of the following)\b|một trong các điều kiện", heading) and span["quote"].strip().endswith((":", "：")):
                context = "conditional"
            parsed = parse_technical(span["quote"], field, context)
            if parsed["state"] == "preferred":
                preferred_spans.add((field, span["start"], span["end"]))
            if parsed["state"] != "outside_technical_grammar":
                clauses.append(dict(parsed, evidence=span))
    for field in ("title_for_matching", "tasks_text", "requirements_text"):
        for span in spans(source_field(record, field), field):
            if (field, span["start"], span["end"]) in preferred_spans or optional_state(span["quote"]) or NEGATIVE.search(span["quote"]):
                excluded.append(span)
                continue
            for start, end, key, quote in mentions(span["quote"]):
                positive.setdefault(key, dict(field=field, start=span["start"]+start, end=span["start"]+end, quote=quote))
    outside = record.get("benchmark_scope") == "outside_software_benchmark" or title["role"] == "education/training"
    return dict(role=title["role"], role_overlay=title, role_specific=title["specific"], skills=positive,
                functions=functions(source_field(record, "tasks_text"), "tasks_text"), clauses=clauses,
                excluded_skill_contexts=excluded, outside_scope=outside, text_sha256=record["text_sha256"],
                version=VERSION, metadata_use_exposure="development")


def cv_facts(record, original):
    result = deepcopy(original)
    result["skills"] = {canon(k): v for k, v in original["skills"].items()}
    result["durations"] = [dict(d, scope=canon(d["scope"])) for d in original["durations"]]
    result["nonuse"] = {}
    text = record["text_original"]
    for span in spans(text, "cv_text"):
        # Split sentences at punctuation followed by whitespace, not inside Node.js/.NET.
        for m in re.finditer(r".+?(?:\.(?=\s|$)|$)", span["quote"]):
            value = clean(m[0])
            prefix = re.match(r"(?:tôi\s+)?(?:chưa (?:từng )?(?:sử dụng|dùng)|không có kinh nghiệm (?:với|về)|(?:i )?have not used|no experience with)\s+", value, re.I)
            if prefix:
                body = value[prefix.end():]
                hits = mentions(body)
                if len(hits) == 1 and hits[0][0] == 0 and hits[0][1] == len(body):
                    result["nonuse"][hits[0][2]] = dict(field="cv_text", start=span["start"]+m.start(), end=span["start"]+m.end(), quote=m[0])
    require(not set(result["skills"]) & set(result["nonuse"]), "Contradictory authored skill evidence")
    body_start = text.find("\n")+1
    result["functions"] = functions(text[body_start:], "cv_text")
    for values in result["functions"].values():
        for value in values:
            value["start"] += body_start
            value["end"] += body_start
    return result


def judge(cv, jd):
    common = sorted(set(cv["skills"]) & set(jd["skills"]))
    shared_functions = sorted(set(cv["functions"]) & set(jd["functions"]))
    same = bool(cv["role"]) and cv["role"] == jd["role"] and jd["role_specific"]
    relation = "same_specific_occupation" if same else "shared_task_function" if shared_functions else "unresolved_function_transfer"
    conditions, duration_states = [], []
    unresolved = []
    for index, clause in enumerate(jd["clauses"]):
        if clause["state"] == "mandatory":
            conditions.append(dict(clause=index, state=tree_state(clause["tree"], cv["skills"], cv["nonuse"])))
        elif clause["state"] == "duration":
            bound = clause["duration"]
            durations = [d for d in cv["durations"] if canon(d["scope"]) == bound["scope"] and d["kind"] in {"employment", "contract"}]
            state = "unknown"
            if durations:
                amount = max(d["months"] for d in durations)
                state = "yes" if amount > bound["months"] or (amount == bound["months"] and not bound["strict"]) else "no"
            duration_states.append(dict(clause=index, state=state, scope=bound["scope"]))
            if bound["upper_interpretation_unresolved"]:
                unresolved.append(index)
        elif clause["state"] == "unresolved":
            unresolved.append(index)
    label, reason = "", "insufficient_affirmative_evidence"
    occupation_known = jd["role_specific"] or bool(jd["functions"])
    if jd["outside_scope"]:
        reason = "outside_software_scope"
    elif not occupation_known:
        reason = "unresolved_occupation_and_tasks"
    elif any(c["state"] == "no" for c in conditions+duration_states):
        label, reason = "0", "explicit_mandatory_contradiction"
    elif common and (same or shared_functions):
        label, reason = "1", "affirmative_technical_or_task_overlap"
        if same and conditions and duration_states and not unresolved and all(c["state"] == "yes" for c in conditions+duration_states):
            label, reason = "2", "all_observed_bounded_technical_conditions_supported"
    return dict(relevance_0_1_2=label, label_status="automatic_rule_proxy" if label else "insufficient_evidence",
                reason=reason, relation=relation, shared_skills=common, shared_functions=shared_functions,
                mandatory_states=conditions, duration_states=duration_states, unresolved_clause_indices=sorted(set(unresolved)))
