"""Conservative scope/bound guards; ambiguous requirements remain unknown."""
import re


def excludes_minimum(text):
    return bool(re.search(r"không\s+(?:yêu\s+cầu|cần)|no\s+(?:prior\s+)?experience|not\s+required|"
                          r"tối\s+đa|up\s+to|at\s+most|less\s+than|dưới\s+\d|"
                          r"ưu\s+tiên|preferred|nice\s+to\s+have", text, re.I))


def explicit_scopes(text):
    patterns = {
        "backend python": r"backend\s+(?:với\s+)?python|python\s+backend",
        "backend java": r"backend\s+(?:với\s+)?java\b|java\s+backend",
        "frontend": r"front[ -]?end",
        "devops": r"\bdevops\b",
        "kiểm thử phần mềm": r"kiểm\s+thử\s+phần\s+mềm|software\s+testing",
        "data analysis": r"data\s+analy(?:sis|st)|phân\s+tích\s+dữ\s+liệu",
    }
    found = [scope for scope, pattern in patterns.items() if re.search(pattern, text, re.I)]
    if len(found) == 1:
        return found
    if len(found) > 1:
        return []
    # Single explicit technology durations stay technology-scoped.
    technologies = [scope for scope in ("python", "java", "react", "django", "aws", "selenium", "kubernetes", "sql")
                    if re.search(r"(?<!\w)" + scope + r"(?!\w)", text, re.I)]
    if len(technologies) == 1:
        return technologies
    if technologies:
        return []
    if re.search(r"back[ -]?end", text, re.I):
        return ["backend"]
    if re.search(r"software\s+(?:development|engineering)|phát\s+triển\s+phần\s+mềm", text, re.I):
        return ["software development"]
    return ["professional experience"]
