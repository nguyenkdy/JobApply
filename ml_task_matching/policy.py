"""Evidence-based functional overlap without a closed list of occupation labels."""
from copy import deepcopy
import re

from ml_data import technical_policy_v2 as v2
from ml_data.policies import technical_v3 as v3
from ml_data.common import require

VERSION = "task-evidence-proxy-v4"
POLICY = dict(version=VERSION, method="Python regex and closed grammars; no LLM or network",
    role_usage="Display/distribution only; no title equality, occupation allowlist, or title-derived skills in decisions",
    positive="Affirmative shared task function AND content-derived common technology",
    negative="Explicit contradiction of an applicable mandatory requirement only; absence/title mismatch/task difference are not negatives",
    strong="Shared task and technology, all detected JD task families covered, task segments accounted, complete bounded requirement grammar, supported mandatory conditions; duration not mandatory if none stated",
    limitations="Finite task/technology vocabulary; open occupation input does not mean universal occupation support. Technical proxy, not gold or hiring suitability",
    scope="Preserve existing explicit dataset exclusions; do not derive new exclusions from free-form job title",
    exposure="development; existing partitions diagnostic only", llm_calls=0, models_trained=0)

# Action + work object, not occupational titles or bare technology keywords.
TASK_PATTERNS = {
    "backend_services": (r"viết|sửa|xây dựng|phát triển|thiết kế|triển khai|build|develop|implement|design|write|maintain|fix",
                         r"\bapi\b|\bendpoints?\b|back[ -]?end|microservices?|server[ -]side"),
    "user_interface": (r"viết|sửa|dựng|xây dựng|phát triển|thiết kế|build|develop|implement|design|write|fix",
                       r"giao diện|\bui\b|front[ -]?end|web pages?|user interfaces?"),
    "quality_testing": (r"viết|tạo|thiết kế|thực hiện|chạy|kiểm thử|kiểm tra|write|design|execute|run|perform|create",
                        r"test cases?|test plans?|automated tests?|regression tests?|kịch bản kiểm thử|kiểm thử|tình huống lỗi|chức năng|api"),
    "data_pipeline": (r"xây dựng|phát triển|thiết kế|nạp|hợp nhất|chuẩn hóa|build|develop|implement|design|load|transform|ingest",
                      r"\betl\b|data pipelines?|luồng (?:nạp|xử lý|dữ liệu)|kho dữ liệu|data warehouse|dữ liệu|data"),
    "ml_modeling": (r"huấn luyện|đánh giá|train|evaluate|develop|build",
                    r"mô hình|\bmodels?\b|mạng nơ[ -]?ron|neural networks?"),
    "infrastructure_operations": (r"cấu hình|quản trị|vận hành|triển khai|khôi phục|configure|operate|deploy|administer|restore|maintain|build",
                                  r"linux|containers?|kubernetes|hạ tầng|máy chủ|infrastructure|servers?|ci/cd|deployment pipelines?"),
    "mobile_application": (r"viết|làm|phát triển|xây dựng|build|develop|implement",
                           r"ứng dụng[^.;\n]{0,25}(?:điện thoại|android|ios)|mobile apps?|android apps?|ios apps?"),
    "database_design": (r"thiết kế|tối ưu|design|optimi[sz]e|tune",
                        r"cơ sở dữ liệu|database|sql queries|truy vấn|schema"),
    "data_analysis": (r"phân tích|giải thích|trực quan hóa|analy[sz]e|explain|visuali[sz]e",
                      r"doanh thu|khách hàng|tỷ lệ|chỉ số|xu hướng|dữ liệu|revenue|customers?|metrics?|trends?|data"),
}
NEGATED = re.compile(r"\b(?:chưa|không|not|never|without|cannot|can't|no)\b", re.I)
HYPOTHETICAL = re.compile(r"\b(?:nếu|if|unless)\b|mong muốn|muốn học|định học|want to|would like|đào tạo|hướng dẫn|teach|train staff", re.I)
CV_FUTURE = re.compile(r"\bsẽ\b|\bwill\b|plan to", re.I)


def segments(text, field, offset=0):
    for match in re.finditer(r"[^\n;!?]+?(?:\.(?=\s|$)|$|(?=[\n;!?]))", text):
        if match[0].strip():
            yield dict(field=field, start=offset+match.start(), end=offset+match.end(), quote=match[0])


def task_evidence(text, field, kind="jd", offset=0):
    functions, states = {}, []
    for span in segments(text, field, offset):
        quote = span["quote"]
        excluded = bool(NEGATED.search(quote) or HYPOTHETICAL.search(quote) or v2.OPTIONAL.search(quote) or
                        kind == "cv" and CV_FUTURE.search(quote))
        found = []
        complete = False
        if not excluded:
            for family, (actions, objects) in TASK_PATTERNS.items():
                for action in re.finditer(r"\b(?:"+actions+r")\b", quote, re.I):
                    obj = re.search(objects, quote[action.end():action.end()+120], re.I)
                    if not obj:
                        continue
                    bridge = quote[action.end():action.end()+obj.start()]
                    # Writing tests for an API is not implementing the API itself.
                    if family == "backend_services" and re.search(r"tests?|kiểm thử|kiểm tra", bridge, re.I):
                        continue
                    if family == "quality_testing" and obj[0].casefold() == "api" and action[0].casefold() not in {"kiểm thử", "kiểm tra", "test"}:
                        continue
                    functions.setdefault(family, []).append(dict(span, action=action[0], object=obj[0], rule_version=VERSION))
                    found.append(family)
                    prefix = v3.clean(quote[:action.start()]).casefold()
                    suffix = v3.clean(quote[action.end()+obj.end():])
                    # Detection of one action in a paragraph is not complete task coverage.
                    complete = complete or prefix in {"", "tôi", "i", "we", "you will"} and not suffix
                    break
        states.append(dict(evidence=span, state="excluded_context" if excluded else "task_detected" if found else "unresolved_task_text",
            functions=found, bounded_statement_complete=complete))
    return functions, states


def skills_from_fields(fields, kind="jd"):
    skills = {}
    preferred = False
    for field, text in fields.items():
        preferred = field == "preferred_requirements_text"
        for span in segments(text, field):
            heading = v3.clean(span["quote"]).casefold().rstrip(":：")
            if heading in {"ưu tiên", "điểm cộng", "preferred", "nice to have"}:
                preferred = True
            elif heading in {"yêu cầu", "bắt buộc", "requirements", "required", "must have"} and field != "preferred_requirements_text":
                preferred = False
            if (preferred or NEGATED.search(span["quote"]) or HYPOTHETICAL.search(span["quote"]) or
                    v2.optional_state(span["quote"]) or kind == "cv" and CV_FUTURE.search(span["quote"])):
                continue
            for a, b, term, quote in v2.mentions(span["quote"]):
                skills.setdefault(term, dict(field=field, start=span["start"]+a, end=span["start"]+b, quote=quote))
    return skills


def requirement_coverage(fields, clauses):
    """No required duration != failed extraction: account for each nonempty source segment."""
    unresolved, evidence = [], []
    for field in ("requirements_text", "preferred_requirements_text"):
        for span in segments(fields.get(field, ""), field):
            value = v3.clean(span["quote"]).casefold().rstrip(":：")
            if value in {"yêu cầu", "bắt buộc", "requirements", "required", "must have", "ưu tiên", "điểm cộng", "preferred", "nice to have"}:
                continue
            covers = [c for c in clauses if c["evidence"]["field"] == field and c["evidence"]["start"] <= span["start"] and c["evidence"]["end"] >= span["end"]]
            state = "accounted" if covers and all(c["state"] in {"mandatory", "duration", "preferred"} for c in covers) else "unresolved"
            item = dict(evidence=span, state=state)
            evidence.append(item)
            if state == "unresolved":
                unresolved.append(item)
    present = bool(fields.get("requirements_text", "").strip())
    return dict(requirements_present=present, complete_bounded_grammar=present and not unresolved and bool(evidence),
                segments=evidence, unknown_segments=len(unresolved), interpretation="Closed technical grammar coverage, not full hiring suitability")


def job_facts(record, original=None):
    fields = {f: v2.source_field(record, f) for f in ("tasks_text", "requirements_text", "preferred_requirements_text")}
    if original is None:
        # Title is deliberately empty for feature extraction. Free-form title stays metadata.
        parse_record = dict(role="", role_precision="unknown_or_conflicting", text_sha256=record.get("text_sha256", ""),
            occurrences=[dict(raw_row=dict(fields, title_for_matching=""))])
        original = v3.jd_facts(v2.jd_facts(parse_record))
    result = deepcopy(original)
    result["skills"] = skills_from_fields(fields)
    preferred = [c["evidence"] for c in result["clauses"] if c["state"] == "preferred"]
    result["skills"] = {key: span for key, span in result["skills"].items() if not any(
        p["field"] == span["field"] and p["start"] <= span["start"] < span["end"] <= p["end"] for p in preferred)}
    functions, states = task_evidence(fields["tasks_text"], "tasks_text")
    result.update(functions=functions, task_segments=states, requirement_coverage=requirement_coverage(fields, result["clauses"]), version=VERSION)
    return result


def cv_facts(text, original=None, body_offset=0, role=""):
    """Free-form titles accepted; no inferred occupation or total-to-technology duration."""
    body = text[body_offset:]
    positive = skills_from_fields({"cv_text": body}, "cv")
    for value in positive.values():
        value["start"] += body_offset
        value["end"] += body_offset
    if original is None:
        durations = []
        for span in segments(body, "cv_text", body_offset):
            value = v3.clean(span["quote"])
            if NEGATED.search(value) or HYPOTHETICAL.search(value) or CV_FUTURE.search(value):
                continue
            # CV point-duration statements only: never interpret a lower bound as a known total.
            m = re.fullmatch(r"(?:tôi có|i have)\s+(\d+(?:[.,]\d+)?\s+(?:tháng|năm|years?|months?)\s+.+)", value, re.I)
            if not m or not re.search(r"làm việc|professional|working|employment|contract", m[1], re.I):
                continue
            duration = v3.duration(m[1])
            if duration and not duration["strict"] and duration["range_upper_months"] is None:
                durations.append(dict(span, scope=duration["scope"], months=duration["months"], kind="contract" if re.search(r"\bcontract\b", value, re.I) else "employment"))
        original = dict(role=role, skills=positive, durations=durations, nonuse={})
    result = deepcopy(original)
    result["skills"] = positive
    # Reuse only the closed explicit non-use parser; no title dependency.
    parsed = v2.cv_facts(dict(text_original=text), result)
    result["nonuse"] = parsed["nonuse"]
    result["functions"], result["task_segments"] = task_evidence(body, "cv_text", "cv", body_offset)
    result["version"] = VERSION
    return result


def judge(cv, jd):
    shared_tasks = sorted(set(cv["functions"]) & set(jd["functions"]))
    shared_skills = sorted(set(cv["skills"]) & set(jd["skills"]))
    mandatory, durations, unresolved = [], [], []
    for index, clause in enumerate(jd["clauses"]):
        if clause["state"] == "mandatory":
            mandatory.append(dict(clause=index, state=v2.tree_state(clause["tree"], cv["skills"], cv["nonuse"])))
        elif clause["state"] == "duration":
            bound = clause["duration"]
            observed = [d["months"] for d in cv["durations"] if v2.canon(d["scope"]) == bound["scope"] and d["kind"] in {"employment", "contract"}]
            state = "unknown" if not observed else "yes" if max(observed) > bound["months"] or max(observed) == bound["months"] and not bound["strict"] else "no"
            durations.append(dict(clause=index, state=state, scope=bound["scope"]))
            if bound["upper_interpretation_unresolved"]:
                unresolved.append(index)
        elif clause["state"] == "unresolved":
            unresolved.append(index)
    label, reason = "", "insufficient_task_and_skill_evidence"
    if jd.get("outside_scope", False):
        reason = "preserved_dataset_scope_exclusion"
    elif any(c["state"] == "no" for c in mandatory+durations):
        label, reason = "0", "explicit_mandatory_contradiction"
    elif shared_tasks and shared_skills:
        label, reason = "1", "shared_task_and_content_skill"
        tasks_accounted = bool(jd["task_segments"]) and all(s["state"] == "task_detected" and s["bounded_statement_complete"] for s in jd["task_segments"])
        if (tasks_accounted and set(jd["functions"]) <= set(cv["functions"]) and jd["requirement_coverage"]["complete_bounded_grammar"]
                and mandatory and not unresolved and all(c["state"] == "yes" for c in mandatory+durations)):
            label, reason = "2", "supported_bounded_tasks_and_requirements"
    return dict(relevance_0_1_2=label, label_status="automatic_rule_proxy" if label else "insufficient_evidence", reason=reason,
        shared_functions=shared_tasks, shared_skills=shared_skills, mandatory_states=mandatory, duration_states=durations,
        unresolved_clause_indices=unresolved, title_used_for_decision=False, unseen_title_rejected=False,
        requirement_coverage_complete=jd["requirement_coverage"]["complete_bounded_grammar"], version=VERSION)


def inspect_pair(payload):
    require(isinstance(payload.get("cv"), dict) and isinstance(payload.get("jd"), dict), "Expected cv and jd objects")
    cv_input, jd_input = payload["cv"], payload["jd"]
    require(isinstance(cv_input.get("text"), str) and bool(cv_input["text"].strip()), "CV text required")
    for field in ("tasks_text", "requirements_text", "preferred_requirements_text"):
        require(isinstance(jd_input.get(field, ""), str), "JD field must be text")
    cv = cv_facts(cv_input["text"], role=cv_input.get("role", ""))
    jd = job_facts(dict(occurrences=[dict(raw_row=jd_input)]))
    return dict(decision=judge(cv, jd), cv_facts=cv, jd_facts=jd,
        mode="offline_rule_diagnostic_not_trained_model_or_app", model_trained=False)
