"""Expanded task-and-requirement matching policy v5 without occupation gates.

Extends v4 with clause-local negation/future filtering, subject-carrier task
grammars, explicit clause-level non-use extraction, parenthetical and
explicit-disjunction requirement trees, and declared non-technical scope
accounting while keeping all safety contracts and title invariance intact.
"""
from copy import deepcopy
from functools import lru_cache
import re

from ml_data.common import require
from ml_data.policies import technical_v3 as v3
from ml_data import technical_policy_v2 as v2
from ml_task_matching import policy as v4

VERSION = "task-evidence-proxy-v5"
POLICY = dict(
    version=VERSION,
    parent=v4.VERSION,
    matching_basis="actual_work_tasks_and_explicit_technical_requirements_only",
    title_policy="Job title and CV role are non-gating metadata; unseen or renamed titles never reject, promote, or demote a pair",
    positive="Affirmative shared task function AND content-derived common technology",
    negative="Explicit contradiction of an applicable mandatory requirement only; absence/title mismatch/task difference are not negatives",
    strong="Shared task and technology, all detected JD task families covered, task segments accounted, complete bounded requirement grammar, supported mandatory conditions; duration not mandatory if none stated",
    limitations="Finite task/technology vocabulary; open occupation input does not mean universal occupation support. Technical proxy, not gold or hiring suitability",
    scope="Preserve existing explicit dataset exclusions; do not derive new exclusions from free-form job title",
    exposure="development; existing partitions diagnostic only",
    llm_calls=0,
    models_trained=0,
)

PATTERNS_V5 = dict(v2.PATTERNS)
EXTRA_TERMS_V5 = {
    "sql server": r"(?<!\w)(?:ms\s+|microsoft\s+)?sql\s+server(?!\w)",
    "scikit-learn": r"(?<!\w)(?:scikit[ -]?learn|sklearn)(?!\w)",
    "opencv": r"(?<!\w)opencv(?!\w)",
    "express": r"(?<!\w)express(?:\.js|js)?(?!\w)",
    "sqlite": r"(?<!\w)sqlite(?!\w)",
    "entity framework": r"(?<!\w)entity\s+framework(?:\s+core)?(?!\w)",
    "bigquery": r"(?<!\w)bigquery(?!\w)",
    "clickhouse": r"(?<!\w)clickhouse(?!\w)",
    "mlflow": r"(?<!\w)mlflow(?!\w)",
    "vitest": r"(?<!\w)vitest(?!\w)",
    "xctest": r"(?<!\w)xctest(?!\w)",
    "core data": r"(?<!\w)core\s+data(?!\w)",
    "testing library": r"(?<!\w)testing\s+library(?!\w)",
    "podman": r"(?<!\w)podman(?!\w)",
    "devtools": r"(?<!\w)devtools(?!\w)",
    "jira": r"(?<!\w)jira(?!\w)",
    "postman": r"(?<!\w)postman(?!\w)",
    "playwright": r"(?<!\w)playwright(?!\w)",
    "cypress": r"(?<!\w)cypress(?!\w)",
    "selenium": r"(?<!\w)selenium(?!\w)",
    "pytest": r"(?<!\w)pytest(?!\w)",
    "junit": r"(?<!\w)junit(?!\w)",
    "parquet": r"(?<!\w)parquet(?!\w)",
}
for _key, _pat in EXTRA_TERMS_V5.items():
    PATTERNS_V5.setdefault(_key, _pat)


def _triggers_for(key):
    special = {
        "frontend": ("front",),
        "django rest framework": ("django", "drf"),
        "jakarta ee": ("jakarta", "j2ee"),
        "javascript": ("javascript", "ecmascript", "java script"),
        "react": ("react",),
        "next.js": ("next",),
        "vue": ("vue",),
        "sass": ("sass", "scss"),
        "postgresql": ("postgres",),
        "elasticsearch": ("elastic",),
        "linux": ("linux", "ubuntu", "centos", "red hat", "redhat"),
        "bash": ("bash", "shell"),
        "kubernetes": ("kubernetes", "k8s", "eks", "aks", "gke"),
        "gitlab ci": ("gitlab",),
        "github actions": ("github",),
        "aws": ("aws", "amazon"),
        "google cloud": ("google cloud", "gcp"),
        "openapi": ("openapi", "swagger"),
        "power bi": ("power",),
        ".net": (".net", "dotnet", "dot net"),
        "node.js": ("node",),
        "nestjs": ("nest",),
        "rails": ("rails",),
        "spark": ("spark",),
        "airflow": ("airflow",),
        "sql server": ("sql",),
        "scikit-learn": ("scikit", "sklearn"),
    }
    return special.get(key, (key.casefold().split()[0],))


COMPILED_PATTERNS_V5 = [
    (key, re.compile(pat, re.I), _triggers_for(key))
    for key, pat in PATTERNS_V5.items()
]


@lru_cache(maxsize=16384)
def mentions(text):
    low = text.casefold()
    hits = [
        (m.start(), m.end(), key, m[0])
        for key, pat, triggers in COMPILED_PATTERNS_V5
        if any(t in low for t in triggers)
        for m in pat.finditer(text)
    ]
    chosen = []
    for start, end, key, quote in sorted(hits, key=lambda h: (-(h[1] - h[0]), h[0], h[2])):
        if not any(start < b and a < end for a, b, _, _ in chosen):
            chosen.append((start, end, key, quote))
    return sorted(chosen)


TASK_PATTERNS = {
    "backend_services": (
        r"viết|sửa|xây dựng|xây|dựng|(?<!đội ngũ\s)(?<!nhóm\s)(?<!bộ phận\s)(?<!team\s)phát triển|(?<!team\s)(?<!nhóm\s)(?<!bộ phận\s)thiết kế|triển khai|làm|nhận|phụ trách|bổ sung|cung cấp|phục vụ|xử lý|tích hợp|mô phỏng|có|lập trình|tối ưu|maintain(?:ing|s)?|build(?:ing|s)?|develop(?:ing|s|ment)?|implement(?:ing|s|ation)?|design(?:ing|s)?|writ(?:e|ing|es)|fix(?:ing|es)?|creat(?:e|ing|es)|integrat(?:e|ing|es)|optimiz(?:e|ing|es)|architect(?:ing|s)?",
        r"\bapis?\b|\bendpoints?\b|back[ -]?end|microservices?|micro-service\s+applications?|server[ -]side|dịch vụ\s+(?:web|java|backend|phân loại|tính|đăng ký|cấp quyền|thử|điều phối|xử lý|nhận|tích hợp)|phần\s+api|rest(?:ful)?\s+api|cổng\s+(?:tiếp nhận|phân ca|duyệt|trao đổi|xác nhận)|sổ\s+(?:đặt lịch|hạn dùng|mượn|vật tư)|bảng\s+(?:điều phối|bảo trì|kết quả)|lịch\s+(?:thi|sửa\s+đồ)|chức năng\s+(?:truy vết|xếp lệnh)|lệnh\s+thay\s+nguyên liệu|quản lý\s+(?:đồ thất lạc|kho đồ tặng)|nhật ký\s+lô\s+gieo hạt|quy trình\s+gửi\s+yêu cầu|bộ\s+nhập\s+danh\s+mục|kiểm tra\s+(?:dữ liệu\s+ở\s+server|quyền\s+trên\s+server|endpoint)|giới hạn\s+số\s+khách|(?:web[ -]based\s+software\s+systems?|web\s+applications?|applications?|solutions?|systems?|sản phẩm|ứng dụng|hệ thống|tính năng|projects?)[^.;\n]{0,55}\b(?:java(?:\s+frameworks?)?|spring(?:\s+boot)?|c#|\.net|asp\.net|python|django|flask|fastapi|node\.?js|express|golang|php|laravel|ruby|scala)\b|\bbe\s*:\s*(?:java|spring|node|python|c#|\.net)",
    ),
    "user_interface": (
        r"viết|sửa|dựng|xây dựng|xây|(?<!đội ngũ\s)(?<!nhóm\s)(?<!bộ phận\s)(?<!team\s)phát triển|(?<!team\s)(?<!nhóm\s)(?<!bộ phận\s)thiết kế|làm|nhận|hiển thị|hỗ trợ|tạo|bổ sung|lập trình|tối ưu|build(?:ing|s)?|develop(?:ing|s|ment)?|implement(?:ing|s|ation)?|design(?:ing|s)?|writ(?:e|ing|es)|fix(?:ing|es)?|creat(?:e|ing|es)|maintain(?:ing|s)?",
        r"(?<!cho\s)(?<!nhóm\s)(?<!trạng thái\s)giao diện|\bui\b|front[ -]?end|web pages?|(?:user\s+|user-friendly\s+)?interfaces?|màn hình\s+(?:xem\s+(?:đường\s+cong|lỗi\s+bề\s+mặt)|tra cứu|có\s+độ\s+tương\s+phản)|trang\s+(?:web|so sánh|theo dõi|đăng ký|khai báo|bài tập|thực đơn)|biểu mẫu|\bforms?\b|bảng\s+(?:so sánh|công việc\s+vườn\s+ươm|nhận xét\s+đồng\s+đẳng)|cổng\s+đăng ký|điều hướng bằng bàn phím|lỗi\s+(?:kéo\s+thẻ|mất\s+vị\s+trí\s+nhận\s+xét\s+khi\s+đổi\s+trang)|trạng thái\s+tải\s+thất bại|phần\s+react|với\s+vue|(?:web\s+(?:apps?|applications?)|applications?|solutions?|sản phẩm|ứng dụng)[^.;\n]{0,55}\b(?:react(?:js)?|angular|vue(?:\.?js)?|next\.?js|front-end\s+frameworks?|bootstrap|tailwind)\b|\bfe\s*:\s*(?:angular|react|vue)",
    ),
    "quality_testing": (
        r"viết|tạo|thiết kế|thực hiện|chạy|kiểm thử|kiểm tra|kiểm|thử|tìm lỗi|phát hiện|tái hiện|đối chiếu|thêm|sửa|lưu|giữ|ghi|nhận|facilitat(?:e|ing)|conduct(?:ing)?|writ(?:e|ing|es)|design(?:ing|s)?|execut(?:e|ing|es)|run(?:ning|s)?|perform(?:ing|s)?|creat(?:e|ing|es)|automat(?:e|ing|es)|build(?:ing|s)?|maintain(?:ing|s)?|test(?:ing|s)?",
        r"test cases?|test plans?|test suites?|test scripts?|test frameworks?|automated tests?|automation tests?|regression tests?|regression testing|integration testing|all levels of testing|unit tests?|(?:web\s+and\s+)?api tests?|kịch bản kiểm thử|kiểm thử|ca\s+(?:kiểm\s+tra\s+thủ\s+công|kiểm\s+thử)|bộ\s+(?:kiểm tra|kiểm thử|hồi quy)|bước tái hiện|dữ liệu tái hiện|để hồi quy|biểu mẫu\s+tiếp nhận\s+sách|chức năng\s+(?:đổi\s+biểu\s+giá|xác\s+nhận\s+phiếu)|phần\s+chuyển\s+trách\s+nhiệm|phần\s+mềm\s+(?:mô\s+phỏng\s+nhập|ghi\s+nhận\s+dừng\s+máy|quản\s+lý\s+thiết\s+bị)|tiến\s+độ\s+khóa\s+học|mã\s+giảm\s+giá\s+dùng\s+chung|một\s+trang\s+phối\s+màu|đặt\s+(?:dịch\s+vụ\s+spa|sân\s+giả\s+lập)|tình huống lỗi|api",
    ),
    "data_pipeline": (
        r"xây dựng|xây|dựng|phát triển|thiết kế|nạp|nhập|hợp nhất|chuẩn hóa|điều phối|chuyển|di chuyển|gom|tổng hợp|đối chiếu|bàn giao|nhận|hỗ trợ|tạo|build(?:ing|s)?|develop(?:ing|s)?|implement(?:ing|s)?|design(?:ing|s)?|load(?:ing|s)?|transform(?:ing|s|ation)?|ingest(?:ing|s)?|orchestrat(?:e|ing)|migrat(?:e|ing)|aggregat(?:e|ing)|perform(?:ing)?|focus(?:ing)?\s+on",
        r"\betl\b|\belt\b|(?:etl/elt\s+)?pipelines?|data pipelines?|data\s+(?:architectures?|lakes?|warehouses?|platforms?|cleaning|enrichment|transformation|processing|collection|ingestion|delivery)|luồng\s+(?:nạp|xử lý|dữ liệu|hợp nhất|nhập)|kho dữ liệu|bảng\s+(?:staging|tổng hợp|công suất|chuẩn hóa)|tệp\s+sự kiện|danh mục\s+(?:vật tư|học liệu|từ các nhà bán)|dữ liệu\s+(?:lô hàng|thử|đến muộn|lớn|streaming)|nhiệt độ|bản đọc cảm biến|thời gian chạy|parquet",
    ),
    "ml_modeling": (
        r"huấn luyện|đánh giá|phân loại|dự báo|nhận dạng|phân đoạn|tạo|thử|so\s+với|xây dựng|phát triển|triển khai|cải tiến|nghiên cứu|tối ưu|train(?:ing|s)?|evaluat(?:e|ing|es)|develop(?:ing|s)?|build(?:ing|s)?|classif(?:y|ying)|predict(?:ing|s)?|forecast(?:ing|s)?|segment(?:ing|s)?|deploy(?:ing|s)?|fine[ -]?tun(?:e|ing)",
        r"mô hình|\bmodels?\b|thuật toán\s+và\s+mô\s+hình|mạng\s+(?:nơ[ -]?ron|nhỏ)|neural networks?|baseline|ảnh\s+(?:bao bì|tấm kim loại|quả|tự tạo|tổng hợp)|phản hồi dịch vụ|động tác bằng video|tải giả lập|thời gian\s+(?:xử lý|chờ)|ký hiệu toán|chủ đề tài liệu|trang truyện|đặc trưng\s+hình\s+học|machine learning|deep learning|\bllms?\b|genai|computer vision|\bnlp\b",
    ),
    "infrastructure_operations": (
        r"cấu hình|quản trị|vận hành|triển khai|khôi phục|dựng|quản lý|giám sát|theo dõi|đóng gói|chuyển|configur(?:e|ing|es)|operat(?:e|ing|es|ion)|deploy(?:ing|s|ment)?|administer(?:ing|s)?|restor(?:e|ing|es)|maintain(?:ing|s|ance)?|build(?:ing|s)?|manag(?:e|ing|es)|monitor(?:ing|s)?|set\s+up",
        r"linux|(?<!giao diện theo dõi\s)containers?|kubernetes|\bk8s\b|\bpods?\b|helm|docker|terraform|ansible|prometheus|grafana|cloudwatch|zabbix|ceph\s+clusters?|cluster\s+health|system\s+health|hạ tầng|(?<!giờ\s)(?<!phát triển hệ thống\s)máy chủ|(?<!sql\s)\bservers?\b|môi trường\s+(?:thử|staging|phần mềm|demo)|kho gói|hàng đợi render|cụm máy|máy\s+(?:hiển thị|lưu\s+tài liệu)|infrastructure|\(?ci/cd/?\)?(?:ct\s+pipelines?)?|deployment pipelines?|aws\s+cloud|cloud\s+infrastructure",
    ),
    "mobile_application": (
        r"viết|làm|xây dựng|xây|phát triển|sửa|xử lý|lưu|chạy|đóng góp|dùng|thiết kế|build(?:ing|s)?|develop(?:ing|s|ment)?|implement(?:ing|s)?|creat(?:e|ing|es)|maintain(?:ing|s)?|design(?:ing|s)?",
        r"(?:ứng dụng|dự án|sản phẩm|game)[^.;\n]{0,60}(?:điện thoại|android|ios|ngoại tuyến|ghi\s+bài\s+tập|ghi\s+biên\s+bản|kiểm\s+giá\s+tại\s+quầy|ghi\s+chép\s+hố|ghi\s+nhận\s+vị\s+trí)|(?:mobile|android|ios|flutter|react\s+native)\s+(?:apps?|applications?|products?|games?)|mobile\s*\(\s*(?:react\s+native|flutter|android|ios)\s*\)|applications?\s+using[^.;\n]{0,40}(?:react\s+native|flutter)|app\s+(?:android|ios)|trên\s+(?:android|ios)|màn\s+(?:nhập|hình)[^.;\n]{0,60}(?:ngoại tuyến|iOS|Android|Flutter)|thẻ từ vựng trên android|sổ ảnh sâu bệnh ngoại tuyến",
    ),
    "database_design": (
        r"thiết kế|tối ưu|truy vấn|design(?:ing|s)?|optimi[sz](?:e|ing|es)|tun(?:e|ing|es)|quer(?:y|ying)|migrat(?:e|ing)",
        r"cơ sở dữ liệu|csdl|databases?|sql queries|truy vấn|schema|khóa ngoại|migration",
    ),
    "data_analysis": (
        r"phân tích|giải thích|trực quan hóa|theo dõi|tổng hợp|analy[sz](?:e|ing|es)|explain(?:ing|s)?|visuali[sz](?:e|ing|es)",
        r"doanh thu|khách hàng|tỷ lệ|chỉ số(?:\s+kinh\s+doanh)?|xu hướng|dữ liệu|revenue|customers?|(?<!quality assurance\s)metrics?|trends?|data",
    ),
}

COMPILED_TASK_PATTERNS = {
    family: (re.compile(r"\b(?:" + actions + r")\b", re.I), re.compile(objects, re.I))
    for family, (actions, objects) in TASK_PATTERNS.items()
}

CARRIER_TASK_PATTERNS = {
    "backend_services": (
        r"asp\.net\s+core|spring\s+boot|quarkus|fastapi|django|flask|express|node\.js",
        r"lưu|giữ|xử lý|phục vụ|nhận|kiểm|thử|thêm|gửi|tạo|chạy",
        r"khoảng\s+ngày|phiên\s+bản|số\s+hiệu|hạn\s+mức|mốc\s+thay|quan\s+hệ|trạng\s+thái|trùng\s+phòng|trận\s+giả\s+lập|quyền|bản\s+đọc|lần\s+bàn\s+giao|yêu\s+cầu|phiếu|kiện|mã|tạm\s+dừng|số\s+chỗ|endpoint|đăng\s+ký|xung\s+đột|quy\s+tắc|dữ\s+liệu",
    ),
    "user_interface": (
        r"react|vue|angular|phần\s+trình\s+duyệt",
        r"hiển thị|dựng|lọc|xử lý|dùng|giữ",
        r"sức\s+chứa|lựa\s+chọn|bài\s+được\s+phân\s+công|danh\s+sách\s+bước|lịch|bảng\s+so\s+sánh|biểu\s+mẫu|trạng\s+thái|vue|các\s+đoạn\s+dữ\s+liệu|vùng\s+được\s+chọn|cho\s+form",
    ),
    "quality_testing": (
        r"selenium|postman|jira",
        r"chạy|thử|kiểm|gửi|lưu|giữ|ghi|đối chiếu",
        r"luồng|kiểm\s+tra|api|hủy\s+lịch|dữ\s+liệu|thời\s+điểm|yêu\s+cầu|biến\s+thể|lỗi|bước\s+tái\s+hiện",
    ),
    "infrastructure_operations": (
        r"linux|docker|ansible|prometheus|grafana|github\s+actions|nginx",
        r"quan sát|quản lý|theo dõi|phục vụ|tái dựng|chạy|kiểm|lưu",
        r"dịch\s+vụ|máy\s+giả\s+lập|dung\s+lượng|bản\s+tĩnh|cấu\s+hình|ứng\s+dụng|ảnh\s+trước\s+khi\s+đưa\s+vào\s+máy|số\s+liệu",
    ),
    "mobile_application": (
        r"flutter|kotlin|swift|room|core\s+data",
        r"lưu|xây|xử lý|chạy|giữ|quản lý",
        r"số\s+hiệp|biểu\s+mẫu\s+ngoại\s+tuyến|màn\s+nhập|màn\s+hình|trên\s+android|trên\s+ios|bản\s+nháp|lịch\s+ôn|những\s+mã\s+đã\s+quét|các\s+trang",
    ),
}

COMPILED_CARRIER_PATTERNS = {
    family: (re.compile(r"\b(?:" + c + r")\b", re.I), re.compile(r"\b(?:" + a + r")\b", re.I), re.compile(o, re.I))
    for family, (c, a, o) in CARRIER_TASK_PATTERNS.items()
}

CLAUSE_BOUNDARY = re.compile(r"[,،;]|(?:\b(?:nhưng|thay vì|để tránh|mà không|dù|tuy nhiên|còn|rồi)\b)", re.I)
BRIDGE_BOUNDARY = re.compile(r"[;]|,\s*(?:rồi|nhưng|chưa|không|còn|tuy nhiên|mà không|thay vì|để tránh|tôi)\b|\b(?:nhưng|thay vì|để tránh|mà không|tuy nhiên|rồi\s+trao\s+đổi)\b", re.I)

HYPOTHETICAL = re.compile(
    r"\b(?:nếu|if|unless)\b|mong muốn|muốn học|định học|want to|would like|đào tạo|"
    r"(?<!người\s)(?<!ghi\s)(?<!tài liệu\s)(?<!phiếu\s)(?<!thay\s)hướng dẫn|teach|train staff",
    re.I,
)

OPTIONAL = re.compile(
    r"ưu\s+tiên|không\s+bắt\s+buộc|không\s+yêu\s+cầu|không\s+cần|lợi\s+thế|preferred|optional|nice[ -]to[ -]have|not\s+required|advantage|is\s+considered\s+a\s+bonus|no\s+(?:prior\s+)?experience",
    re.I,
)

SUPPORT_TASK_CONTEXT = re.compile(
    r"^(?:số\s+lượng\s+\d+|project\s+information|project's\s+tools|position\s+summary|"
    r"maintain\s+and\s+enhance\s+services|development\s+and\s+implementation|code\s+quality\s+and\s+collaboration)\b|"
    r"\b(?:viết\s+các\s+đoạn\s+code\s+chất\s+lượng|writing\s+clean,\s+efficient,\s+and\s+maintainable\s+code|"
    r"write\s+clean,\s+well-documented,\s+and\s+maintainable\s+code|"
    r"conducting\s+code\s+reviews|participate\s+in\s+code\s+reviews|tham\s+gia\s+review\s+code|"
    r"collaborat(?:e|ing)\s+(?:closely\s+)?with\s+(?:cross-functional\s+teams|developers|the\s+planning\s+team|the\s+application\s+team|the\s+global\s+team)|"
    r"working\s+closely\s+with\s+team\s+members|làm\s+việc\s+với\s+các\s+lập\s+trình\s+viên|"
    r"phối\s+hợp\s+(?:chặt\s+chẽ\s+)?với\s+(?:đội\s+ngũ|các\s+team|team)|"
    r"staying\s+updated\s+on\s+emerging\s+technologies|stay\s+up\s+to\s+date\s+with\s+the\s+latest\s+trends|"
    r"troubleshooting\s+and\s+debugging\s+applications\s+to\s+optimize\s+performance|"
    r"tối\s+ưu\s+hiệu\s+năng\s+các\s+ứng\s+dụng|"
    r"liên\s+tục\s+tối\s+ưu\s+sản\s+phẩm,\s+xử\s+lý\s+lỗi|"
    r"tham\s+gia\s+vào\s+quá\s+trình\s+phân\s+tích\s+nghiệp\s+vụ,\s+thiết\s+kế\s+và\s+phát\s+triển\s+các\s+tính\s+năng|"
    r"tham\s+gia\s+phân\s+tích\s+yêu\s+cầu,\s+đề\s+xuất\s+giải\s+pháp|"
    r"analyze\s+user\s+stories,\s+use\s+cases,\s+and\s+requirements|"
    r"provide\s+clear\s+test\s+reports\s+and\s+feedback|"
    r"take\s+ownership\s+of\s+testing\s+activities|"
    r"ensure\s+timely\s+delivery\s+of\s+test\s+cases|"
    r"generate\s+comprehensive\s+test\s+summary\s+reports|"
    r"assist\s+in\s+testing\s+and\s+debugging\s+applications|"
    r"we\s+are\s+seeking\s+a\s+talented\s+[\w\s]+to\s+join\s+our\s+team|"
    r"this\s+is\s+a\s+remote\s+position,\s+offering\s+the\s+flexibility)\b",
    re.I,
)

UNCONSUMED_SECOND_ACTION = re.compile(
    r"(?:\b(?:và|and)\b|,)\s*(?:thiết\s+kế|xây\s+dựng|phát\s+triển|triển\s+khai|vận\s+hành|huấn\s+luyện|kiểm\s+thử|"
    r"build|develop|design|implement|deploy|train|configure|operate)\s+\w+",
    re.I,
)

BOUNDED_PREFIX = re.compile(
    r"^(?:tôi|i|we|you\s+will|tham\s+gia(?:\s+vào\s+việc)?|chịu\s+trách\s+nhiệm|phụ\s+trách|"
    r"the\s+ideal\s+candidate\s+will\s+have\s+a\s+strong\s+background\s+in\s+[\w\s]+,\s+with\s+a\s+focus\s+on|"
    r"(?:(?:thiết\s+kế|xây\s+dựng|phát\s+triển|lập\s+trình|bảo\s+trì|kiểm\s+thử|tạo|viết|"
    r"design(?:ing)?|develop(?:ing)?|build(?:ing)?|maintain(?:ing)?|creat(?:e|ing)|writ(?:e|ing)|execut(?:e|ing))"
    r"(?:\s*[,&]\s*|\s+(?:và|and)\s+))+)?$",
    re.I,
)

SEGMENT_RE = re.compile(r"[^\n;!?]+?(?:(?<!^\d)(?<!\n\d)(?<!^\d\d)(?<!\n\d\d)\.(?=\s|$)|$|(?=[\n;!?]))")


def segments(text, field, offset=0):
    for match in SEGMENT_RE.finditer(text):
        if match[0].strip():
            yield dict(field=field, start=offset + match.start(), end=offset + match.end(), quote=match[0])


def _is_action_excluded(quote, action_start, action_end, obj_end, kind="jd"):
    if HYPOTHETICAL.search(quote) or OPTIONAL.search(quote):
        return True
    if kind == "cv" and v4.CV_FUTURE.search(quote[:action_end]):
        return True
    clause_start = 0
    for m in CLAUSE_BOUNDARY.finditer(quote[:action_start]):
        clause_start = m.end()
    prefix_window = quote[clause_start:action_end]
    prefix_cleaned = re.sub(r"\bhay\s+chưa\b", "", prefix_window, flags=re.I)
    if v4.NEGATED.search(prefix_cleaned):
        return True
    bridge = quote[action_end:obj_end]
    if BRIDGE_BOUNDARY.search(bridge) or v4.NEGATED.search(re.sub(r"\bhay\s+chưa\b", "", bridge, flags=re.I)):
        return True
    return False


def task_evidence(text, field, kind="jd", offset=0):
    functions, states = {}, []
    for span in segments(text, field, offset):
        quote = span["quote"]
        found = []
        complete = False
        any_excluded = False
        for family, (act_re, obj_re) in COMPILED_TASK_PATTERNS.items():
            matched_family = False
            for action in act_re.finditer(quote):
                obj = obj_re.search(quote[action.end():action.end() + 110])
                if not obj:
                    continue
                obj_end = action.end() + obj.end()
                if _is_action_excluded(quote, action.start(), action.end(), obj_end, kind):
                    any_excluded = True
                    continue
                bridge = quote[action.end():action.end() + obj.start()]
                if family == "backend_services" and re.search(r"tests?|kiểm thử|kiểm tra|junit|xunit|pytest|vitest|cypress|postman|selenium|playwright", bridge + " " + action[0] + " " + quote[:action.start()], re.I):
                    continue
                if family == "quality_testing" and obj[0].casefold() == "api" and not re.search(r"kiểm thử|kiểm tra|test|regression", bridge + " " + action[0], re.I):
                    continue
                if family == "user_interface" and re.search(r"\b(?:endpoint|api|flask|django|fastapi|spring)\b", bridge, re.I):
                    continue
                if family == "infrastructure_operations" and re.search(r"giao\s+diện", quote[:action.start()], re.I):
                    continue
                if family == "ml_modeling" and obj[0].casefold() in {"baseline"} and not re.search(r"tạo|huấn luyện|xây dựng|phát triển|thử|train|build|develop", action[0], re.I):
                    continue
                functions.setdefault(family, []).append(dict(span, action=action[0], object=obj[0], rule_version=VERSION))
                found.append(family)
                raw_prefix = re.sub(r"^\s*\d+[.)]\s*", "", quote[:action.start()])
                prefix = v3.clean(raw_prefix).casefold()
                suffix = v3.clean(quote[obj_end:])
                prefix_ok = bool(BOUNDED_PREFIX.fullmatch(prefix))
                suffix_ok = not suffix or not UNCONSUMED_SECOND_ACTION.search(suffix)
                complete = complete or (prefix_ok and suffix_ok)
                matched_family = True
                break
            if not matched_family and family in COMPILED_CARRIER_PATTERNS:
                c_re, a_re, o_re = COMPILED_CARRIER_PATTERNS[family]
                for carrier in c_re.finditer(quote):
                    window = quote[carrier.end():carrier.end() + 60]
                    c_act = a_re.search(window)
                    if not c_act:
                        continue
                    act_end = carrier.end() + c_act.end()
                    c_obj = o_re.search(quote[act_end:act_end + 60])
                    if not c_obj:
                        continue
                    obj_end = act_end + c_obj.end()
                    if _is_action_excluded(quote, carrier.start(), act_end, obj_end, kind):
                        any_excluded = True
                        continue
                    functions.setdefault(family, []).append(dict(span, action=c_act[0], object=c_obj[0], rule_version=VERSION))
                    found.append(family)
                    complete = True
                    matched_family = True
                    break
        excluded = not found and bool(any_excluded or v4.NEGATED.search(quote) or HYPOTHETICAL.search(quote) or OPTIONAL.search(quote) or (kind == "cv" and v4.CV_FUTURE.search(quote)))
        support = not found and not excluded and kind == "jd" and (bool(SUPPORT_TASK_CONTEXT.search(v3.clean(quote))) or bool(OPTIONAL.search(quote)))
        state = "excluded_context" if (excluded and kind == "cv") else "support_context" if (support or (excluded and kind == "jd" and OPTIONAL.search(quote))) else "excluded_context" if excluded else "task_detected" if found else "unresolved_task_text"
        states.append(dict(evidence=span, state=state, functions=found, bounded_statement_complete=complete or state == "support_context"))
    return functions, states


def _is_skill_excluded(quote, start, kind="jd"):
    if HYPOTHETICAL.search(quote) or v2.optional_state(quote) or OPTIONAL.search(quote):
        return True
    clause_start = 0
    for m in CLAUSE_BOUNDARY.finditer(quote[:start]):
        clause_start = m.end()
    prefix = quote[clause_start:start]
    if kind == "cv" and v4.CV_FUTURE.search(prefix):
        return True
    prefix_cleaned = re.sub(r"\bhay\s+chưa\b", "", prefix, flags=re.I)
    if v4.NEGATED.search(prefix_cleaned):
        return True
    return False


PREFERRED_HEADINGS = {
    "ưu tiên", "điểm cộng", "preferred", "nice to have", "good to have",
    "huge plus if you are/have", "kiến thức nâng cao (lợi thế)", "lợi thế",
}
REQUIRED_HEADINGS = {
    "yêu cầu", "bắt buộc", "requirements", "required", "must have",
    "must to have", "kiến thức bắt buộc", "skills requirement", "kỹ năng/khả năng",
}

PREFERENCE_LINE = re.compile(
    r"^(?:ưu\s+tiên|điểm\s+cộng|lợi\s+thế|preferred|nice\s+to\s+have|plus\s+if)\b|"
    r"\b(?:is\s+(?:a\s+plus|an\s+advantage|preferred|advantageous|desirable|welcome|a\s+bonus)|"
    r"are\s+(?:a\s+plus|an\s+advantage|preferred|welcome)|"
    r"là\s+(?:một\s+|1\s+)?(?:lợi\s+thế|điểm\s+cộng)(?:\s+lớn)?|"
    r"nhưng\s+không\s+bắt\s+buộc)\s*\.?$",
    re.I,
)


def skills_from_fields(fields, kind="jd"):
    skills = {}
    for field, text in fields.items():
        preferred = field == "preferred_requirements_text"
        for span in segments(text, field):
            heading = v3.clean(span["quote"]).casefold().rstrip(":：")
            if heading in PREFERRED_HEADINGS:
                preferred = True
                continue
            if heading in REQUIRED_HEADINGS and field != "preferred_requirements_text":
                preferred = False
                continue
            if preferred or PREFERENCE_LINE.search(v3.clean(span["quote"])):
                continue
            for a, b, term, quote in mentions(span["quote"]):
                if _is_skill_excluded(span["quote"], a, kind):
                    continue
                skills.setdefault(v2.canon(term), dict(field=field, start=span["start"] + a, end=span["start"] + b, quote=quote))
    return skills


NONUSE_CLAUSE = re.compile(
    r"(?:^|\s+|[,;.]\s*|\bnhưng\s+|\bhoặc\s+|\bcũng\s+)"
    r"(?:tôi\s+|hồ sơ(?:\s+cũng)?\s+)?"
    r"(?:chưa\s+(?:từng\s+)?(?:sử dụng|dùng|quản trị|có\s+kinh\s+nghiệm(?:\s+quản\s+trị)?)|"
    r"không\s+có\s+(?:kinh\s+nghiệm(?:\s+với|\s+về)?|bằng\s+chứng\s+làm)|"
    r"(?:i\s+)?have\s+not\s+used|no\s+experience\s+with|"
    r"chưa\s+phát\s+hành\s+app\s+ra\s+cửa\s+hàng\s+hoặc\s+có\s+kinh\s+nghiệm)\s+"
    r"(?P<tech>terraform|kubernetes|kafka|spark|selenium|ios|android|docker|aws|react|java|python)\b",
    re.I,
)


def extract_nonuse(text, positive_skills):
    nonuse = {}
    for span in v2.spans(text, "cv_text"):
        for m in re.finditer(r".+?(?:\.(?=\s|$)|$)", span["quote"]):
            value = v2.clean(m[0])
            prefix = re.match(r"(?:tôi\s+)?(?:chưa (?:từng )?(?:sử dụng|dùng)|không có kinh nghiệm (?:với|về)|(?:i )?have not used|no experience with)\s+", value, re.I)
            if prefix:
                body = value[prefix.end():]
                hits = mentions(body)
                if len(hits) == 1 and hits[0][0] == 0 and hits[0][1] == len(body):
                    term = v2.canon(hits[0][2])
                    if term not in positive_skills:
                        nonuse[term] = dict(field="cv_text", start=span["start"] + m.start(), end=span["start"] + m.end(), quote=m[0])
            for nm in NONUSE_CLAUSE.finditer(m[0]):
                term = v2.canon(nm.group("tech"))
                if term not in positive_skills and term not in nonuse:
                    nonuse[term] = dict(field="cv_text", start=span["start"] + m.start() + nm.start(), end=span["start"] + m.start() + nm.end(), quote=nm[0])
    return nonuse


PREFIX_V5 = re.compile(
    r"^(?:(?:must\s+(?:have|know)\s+)?(?:(?:hands[ -]on|solid|strong|good|deep|working|practical|demonstrated|proven|in-depth|profound)\s+)*"
    r"(?:experience|knowledge|understanding|proficiency|skills?|familiarity|expertise|background|ability)"
    r"(?:\s+(?:and\s+(?:experience|knowledge|understanding|skills?)))?"
    r"(?:\s+(?:of|in|with|using|working\s+with|developing(?:\s+with)?|design\s+and\s+programming\s+skills\s+using))?|"
    r"proficient\s+(?:in|with)(?:\s+using)?|familiar\s+with|must\s+know|required(?:\s+skills)?|have\s+experience\s+(?:in|with)|"
    r"(?:có\s+)?(?:kinh\s+nghiệm(?:\s+làm\s+việc)?(?:\s+thực\s+tế)?|kiến\s+thức(?:\s+vững(?:\s+chắc)?|\s+nền\s+tảng|\s+cơ\s+bản|\s+làm\s+việc)?|"
    r"hiểu\s+biết(?:\s+vững\s+vàng|\s+sâu)?|kỹ\s+năng(?:\s+lập\s+trình|\s+code)?|"
    r"(?:sử\s+dụng\s+)?thành\s+thạo|nắm\s+vững|biết(?:\s+cách)?\s+sử\s+dụng|quen\s+thuộc|"
    r"bắt\s+buộc(?:\s+(?:phải|có|sử\s+dụng))*|yêu\s+cầu(?:\s+có\s+kinh\s+nghiệm)?)"
    r"(?:\s+(?:về|với|trong|các|công\s+cụ(?:\s+làm\s+việc\s+nhóm)?|ngôn\s+ngữ(?:\s+lập\s+trình)?|framework|nền\s+tảng|"
    r"hệ\s+cơ\s+sở\s+quản\s+trị\s+dữ\s+liệu|hệ\s+quản\s+trị\s+cơ\s+sở\s+dữ\s+liệu|cơ\s+sở\s+dữ\s+liệu|phát\s+triển\s+giao\s+diện\s+với))*|"
    r"(?:testing\s+tools?|ci/cd|version\s+control(?:\s+systems?)?|databases?|front[ -]?end(?:\s+tools?)?|back[ -]?end|"
    r"ngôn\s+ngữ(?:\s+lập\s+trình)?|cơ\s+sở\s+dữ\s+liệu)\s*[:：])[\s:：]*",
    re.I,
)

ONE_OF = re.compile(
    r"(?:một\s+trong\s+(?:các|số)|ít\s+nhất\s+một|(?:at\s+least\s+)?one\s+of(?:\s+these|\s+the\s+following|\s+well-known)?|"
    r"hệ\s+cơ\s+sở\s+quản\s+trị\s+dữ\s+liệu)\b",
    re.I,
)

OUTSIDE_TECH_SCOPE = re.compile(
    r"\b(?:bachelor|master|university|degree|graduated|enrolled|college|major|gpa|"
    r"tốt\s+nghiệp|đại\s+học|cao\s+đẳng|sinh\s+viên|chuyên\s+ngành|bằng\s+cấp|"
    r"english|japanese|chinese|korean|ielts|toeic|tiếng\s+anh|tiếng\s+nhật|tiếng\s+trung|ngoại\s+ngữ|giao\s+tiếp|"
    r"problem[ -]solving|analytical|communication|teamwork|team[ -]oriented|independent(?:ly)?|distributed\s+team|fast[ -]paced|time\s+shifts|"
    r"ready\s+to\s+learn|switch\s+between\s+tasks|enthusiasm|laptop|internet\s+connection|proactive|working\s+relationship|manage\s+a\s+team|leadership|mentorship|"
    r"làm\s+việc\s+nhóm|độc\s+lập|tư\s+duy|chịu\s+được\s+áp\s+lực|trách\s+nhiệm|ham\s+học\s+hỏi|chủ\s+động|cẩn\s+thận|cẩn\s+trọng|"
    r"trung\s+thực|sáng\s+tạo|giải\s+quyết\s+vấn\s+đề|kỷ\s+luật|máu\s+lửa|nhiệt\s+huyết|tố\s+chất|gu\s+thẩm\s+mỹ|yêu\s+thích\s+lập\s+trình|"
    r"code\s+review|review\s+code|test\s+plans?|test\s+cases?|sdlc|software\s+development\s+life\s+cycle|quality\s+processes|"
    r"defect\s+management|test\s+codes?|testing\s+(?:both\s+)?web|software\s+testing\s+for\s+web|"
    r"automation\s+tests?,\s+performance\s+tests?|agile|scrum|waterfall|oop|object[ -]oriented|design\s+patterns?|"
    r"lập\s+trình\s+hướng\s+đối\s+tượng|cấu\s+trúc\s+(?:dữ\s+liệu|giải\s+thuật)|thuật\s+toán|cơ\s+sở\s+dữ\s+liệu|"
    r"microservices|rest(?:ful)?\s+apis?|database\s+design|xây\s+dựng\s+hệ\s+thống|thiết\s+kế\s+database|viết\s+api|"
    r"tìm\s+kiếm\s+trong\s+lập\s+trình|vòng\s+đời\s+ứng\s+dụng|apple\s+store|play\s+store|ci/cd|"
    r"nhận\s+cv|portfolio|khi\s+phỏng\s+vấn|kiểm\s+tra\s+coding|kiểm\s+tra\s+viết\s+luận|full[ -]?time|"
    r"kindly\s+be\s+informed|personal\s+information|eager\s+to\s+learn|passion\s+for\s+exploring|critically\s+analyze)\b",
    re.I,
)


def parse_duration(text):
    value = v3.clean(text)
    found = v3.duration(value)
    if found:
        return found
    if (v2.OPTIONAL.search(value) or v2.CONDITION.search(value) or
            re.search(r"\b(?:no|not|without|never)\b|không|chưa|~|dưới\s*\d|less than|up to|at most", value, re.I)):
        return None
    norm = value.casefold().rstrip(".;: ")
    norm = re.sub(r"^(?:ứng\s+viên\s+|yêu\s+cầu\s+|you\s+(?:must\s+)?have\s+|must\s+have\s+|have\s+|has\s+)+", "", norm)
    norm = re.sub(r"^(?:có\s+)?(?:kinh\s+nghiệm(?:\s+làm\s+việc)?\s+)?(?=(?:tối\s+thiểu|tối\s+thiếu|ít\s+nhất|từ|trên|at\s+least|minimum|more\s+than|over|\d))", "", norm)
    norm = re.sub(r"^tối\s+thiếu\b", "tối thiểu", norm)
    norm = re.sub(r"^có\s+tối\s+thiểu\s+từ\b", "tối thiểu", norm)
    norm = re.sub(r"^có\s+từ\b", "từ", norm)
    norm = re.sub(r"^có\s+ít\s+nhất\b", "ít nhất", norm)
    m = re.fullmatch(r"(?P<time>" + v3.TIME + r")(?:\s+(?P<body>.+))?", norm, re.I)
    if not m:
        return None
    time_str = m["time"]
    body = (m["body"] or "").strip()
    if not body or re.fullmatch(r"(?:kinh\s+nghiệm(?:\s+làm\s+việc|\s+nghề\s+nghiệp)?(?:\s+trở\s+lên|\s+qua\s+hợp\s+đồng|\s+theo\s+hợp\s+đồng)?|(?:of\s+)?(?:relevant\s+|professional\s+|working\s+)?experience|(?:kinh\s+nghiệm\s+)?ở\s+vị\s+trí\s+tương\s+(?:đương|tự))", body, re.I):
        scope_phrase = "professional experience"
    elif re.fullmatch(r"(?:of\s+)?(?:(?:hands-on|professional|working)\s+)?(?:experience|experienced)\s+(?:in|with)\s+(?:software\s+testing|qa|automation\s+test(?:ing|\s+development))(?:\s*\(web\s+and\s+mobile\))?(?:,\s+with\s+a\s+strong\s+focus\s+on\s+test\s+automation.*)?|(?:kinh\s+nghiệm\s+)?(?:trong\s+|về\s+)?kiểm\s+thử(?:\s+phần\s+mềm)?", body, re.I):
        scope_phrase = "kiểm thử phần mềm"
    elif re.fullmatch(r"(?:of\s+)?(?:(?:professional|working|hands-on)\s+)?(?:experience\s+in\s+)?(?:software|web|application)\s+development(?:\s+experience)?|(?:kinh\s+nghiệm\s+)?(?:trở\s+lên\s+)?(?:lập\s+trình|phát\s+triển\s+(?:phần\s+mềm|ứng\s+dụng|web))", body, re.I):
        scope_phrase = "software development"
    elif re.fullmatch(r"(?:of\s+)?(?:(?:professional|working)\s+)?(?:experience\s+in\s+)?back[ -]?end\s+development|(?:kinh\s+nghiệm\s+)?(?:trở\s+lên\s+)?(?:phát\s+triển|lập\s+trình|làm(?:\s+việc)?)\s+back[ -]?end", body, re.I):
        scope_phrase = "backend"
    elif re.fullmatch(r"(?:of\s+)?(?:(?:professional|working)\s+)?(?:experience\s+in\s+)?front[ -]?end\s+development|(?:kinh\s+nghiệm\s+)?(?:trở\s+lên\s+)?(?:phát\s+triển|lập\s+trình|làm(?:\s+việc)?)\s+front[ -]?end", body, re.I):
        scope_phrase = "frontend"
    else:
        hits = mentions(body)
        if len(hits) == 1:
            scope_phrase = "experience with " + hits[0][2]
        else:
            return None
    res = v2.parse_duration(time_str + " " + scope_phrase)
    if res:
        res["normalization"] = "explicit-duration-scope-v5"
    return res


def logic_tree(text, full_clause=""):
    tree = v2.logic_tree(text)
    if tree:
        return tree
    cleaned = v3.clean(text).rstrip(".;,… ")
    cleaned = re.sub(
        r"\s+(?:for\s+developing\s+micro-service\s+applications|to\s+support\s+advanced\s+logic|"
        r"for\s+task\s+management\s+and\s+bug\s+tracking|"
        r"để\s+(?:phát\s+triển|xây\s+dựng|thực\s+hiện)\s+[^.;]+|"
        r"có\s+khả\s+năng\s+áp\s+dụng\s+[^.;]+|"
        r"nắm\s+vững\s+các\s+thao\s+tác\s+[^.;]+)$",
        "",
        cleaned,
        flags=re.I,
    )
    hits = mentions(cleaned)
    if not hits:
        return None
    is_any = bool(ONE_OF.search(full_clause or cleaned) or re.search(r"\b(?:or|hoặc)\b|/", cleaned, re.I))
    rem = cleaned
    for start, end, _, _ in reversed(hits):
        rem = rem[:start] + " " + rem[end:]
    rem = re.sub(
        r"\b(?:and|or|và|hoặc|với|về|như|là|các|công\s+cụ|ngôn\s+ngữ|lập\s+trình|web|framework|frameworks|"
        r"on\s+rails|databases?|such\s+as|messaging\s+systems?|like|version\s+control\s+systems?|tools?|"
        r"well-known|rdbms|at\s+least\s+one\s+of|one\s+of|these|the\s+following|một\s+trong|số|nền\s+tảng|"
        r"phổ\s+biến|hệ\s+cơ\s+sở\s+quản\s+trị\s+dữ\s+liệu|hệ\s+quản\s+trị\s+cơ\s+sở\s+dữ\s+liệu|"
        r"ít\s+nhất\s+một|redmine|etc|vv|v\.v)\b",
        " ",
        rem,
        flags=re.I,
    )
    rem = re.sub(r"[,.;:()/&…+–-]", " ", rem).strip()
    if rem:
        return None
    terms = []
    for _, _, t, _ in hits:
        ct = v2.canon(t)
        if ct not in terms:
            terms.append(ct)
    if len(terms) == 1:
        return dict(op="term", term=terms[0])
    return dict(op="any" if is_any else "all", children=[dict(op="term", term=t) for t in terms])


def parse_clause(text, field="requirements_text", context="required"):
    value = v3.clean(text)
    terms = sorted({v2.canon(h[2]) for h in mentions(value)})
    base = dict(terms=terms, tree=None, duration=None)
    if context == "conditional" or v2.CONDITION.search(value):
        return dict(base, state="unresolved", reason="conditional_applicability")
    if field == "preferred_requirements_text" or context == "preferred":
        return dict(base, state="preferred", reason="preferred_section")
    if PREFERENCE_LINE.search(value) and not re.search(r"\bmust\b|bắt buộc", value, re.I):
        return dict(base, state="preferred", reason="whole_predicate_terminal_preference")
    opt = v2.optional_state(value)
    if opt == "preferred":
        return dict(base, state="preferred", reason="preferred")
    if opt == "mixed_unresolved":
        return dict(base, state="unresolved", reason="mixed_unresolved")
    if v2.NUMERIC_TIME.search(value):
        dur = parse_duration(value)
        if dur:
            return dict(base, state="duration", reason="explicit_scoped_duration_v5", duration=dur)
        return dict(base, state="unresolved", reason="duration_syntax_or_scope")
    prefix = PREFIX_V5.match(value) or v2.PREFIX.match(value) or v3.NEW_PREFIX.match(value)
    if prefix:
        body = value[prefix.end():].strip()
        tree = logic_tree(body, value)
        if tree:
            return dict(base, state="mandatory", tree=tree, reason="complete_explicit_technical_requirement_v5")
    if not terms and OUTSIDE_TECH_SCOPE.search(value):
        return dict(base, state="outside_technical_scope", reason="declared_nontechnical_or_general_scope")
    return dict(base, state="unresolved", reason="unconsumed_requirement_prose")


def requirement_coverage(fields, clauses):
    unresolved, evidence = [], []
    for field in ("requirements_text", "preferred_requirements_text"):
        for span in segments(fields.get(field, ""), field):
            value = v3.clean(span["quote"]).casefold().rstrip(":：")
            if value in PREFERRED_HEADINGS | REQUIRED_HEADINGS:
                continue
            covers = [c for c in clauses if c["evidence"]["field"] == field and c["evidence"]["start"] <= span["start"] and c["evidence"]["end"] >= span["end"]]
            state = "accounted" if covers and all(c["state"] in {"mandatory", "duration", "preferred", "outside_technical_scope"} for c in covers) else "unresolved"
            item = dict(evidence=span, state=state)
            evidence.append(item)
            if state == "unresolved":
                unresolved.append(item)
    present = bool(fields.get("requirements_text", "").strip())
    return dict(
        requirements_present=present,
        complete_bounded_grammar=present and not unresolved and bool(evidence),
        segments=evidence,
        unknown_segments=len(unresolved),
        interpretation="Closed technical grammar coverage, not full hiring suitability",
    )


def job_facts(record, original=None):
    fields = {f: v2.source_field(record, f) for f in ("tasks_text", "requirements_text", "preferred_requirements_text")}
    if original is None:
        parse_record = dict(
            role="",
            role_precision="unknown_or_conflicting",
            text_sha256=record.get("text_sha256", ""),
            occurrences=[dict(raw_row=dict(fields, title_for_matching=""))],
        )
        original = v3.jd_facts(v2.jd_facts(parse_record))
    result = deepcopy(original)
    clauses = []
    for field in ("requirements_text", "preferred_requirements_text"):
        text = fields[field]
        levels = set(v2.LEVEL.findall(text.casefold()))
        conditional_doc = len(levels) > 1
        context = "conditional" if conditional_doc else "preferred" if field.startswith("preferred") else "required"
        for span in segments(text, field):
            heading = v3.clean(span["quote"]).casefold().rstrip(":：")
            if heading in PREFERRED_HEADINGS:
                context = "preferred"
                continue
            if heading in REQUIRED_HEADINGS and not conditional_doc:
                context = "required"
                continue
            if v2.LEVEL.search(heading) and span["quote"].strip().endswith((":", "：")):
                context = "conditional"
                continue
            if re.search(r"\b(?:either|one of the following)\b|một trong các điều kiện", heading) and span["quote"].strip().endswith((":", "：")):
                context = "conditional"
            parsed = parse_clause(span["quote"], field, context)
            clauses.append(dict(parsed, evidence=span))
    result["clauses"] = clauses
    result["skills"] = skills_from_fields(fields, "jd")
    preferred = [c["evidence"] for c in clauses if c["state"] == "preferred"]
    result["skills"] = {
        key: span for key, span in result["skills"].items()
        if not any(p["field"] == span["field"] and p["start"] <= span["start"] < span["end"] <= p["end"] for p in preferred)
    }
    functions, states = task_evidence(fields["tasks_text"], "tasks_text", "jd")
    result.update(
        functions=functions,
        task_segments=states,
        requirement_coverage=requirement_coverage(fields, clauses),
        version=VERSION,
    )
    return result


def cv_facts(text, original=None, body_offset=0, role=""):
    body = text[body_offset:]
    positive = skills_from_fields({"cv_text": body}, "cv")
    for value in positive.values():
        value["start"] += body_offset
        value["end"] += body_offset
    if original is None:
        durations = []
        for span in segments(body, "cv_text", body_offset):
            value = v3.clean(span["quote"])
            if v4.NEGATED.search(value) or HYPOTHETICAL.search(value) or v4.CV_FUTURE.search(value):
                continue
            m = re.fullmatch(
                r"(?:tôi có|i have|hồ sơ(?:\s+[\wÀ-ỹ]+)*\s+ghi|tôi ghi(?:\s+được)?)\s+"
                r"(\d+(?:[.,]\d+)?\s+(?:tháng|năm|years?|months?)\s+.+)",
                value,
                re.I,
            )
            if not m or not re.search(r"làm việc|nghề nghiệp|professional|working|employment|contract", m[1], re.I):
                continue
            dur = parse_duration(m[1])
            if dur and not dur["strict"] and dur["range_upper_months"] is None:
                durations.append(dict(
                    span,
                    scope=dur["scope"],
                    months=dur["months"],
                    kind="contract" if re.search(r"\bcontract\b|hợp đồng", value, re.I) else "employment",
                ))
        original = dict(role=role, skills=positive, durations=durations, nonuse={})
    result = deepcopy(original)
    result["skills"] = positive
    result["durations"] = [dict(d, scope=v2.canon(d["scope"])) for d in original["durations"]]
    result["nonuse"] = extract_nonuse(text, positive)
    require(not set(result["skills"]) & set(result["nonuse"]), "Contradictory authored skill evidence")
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
            observed = [
                d["months"] for d in cv["durations"]
                if v2.canon(d["scope"]) == bound["scope"] and d["kind"] in {"employment", "contract"}
            ]
            state = (
                "unknown" if not observed
                else "yes" if max(observed) > bound["months"] or (max(observed) == bound["months"] and not bound["strict"])
                else "no"
            )
            durations.append(dict(clause=index, state=state, scope=bound["scope"]))
            if bound["upper_interpretation_unresolved"]:
                unresolved.append(index)
        elif clause["state"] == "unresolved":
            unresolved.append(index)
    label, reason = "", "insufficient_task_and_skill_evidence"
    if jd.get("outside_scope", False):
        reason = "preserved_dataset_scope_exclusion"
    elif any(c["state"] == "no" for c in mandatory + durations):
        label, reason = "0", "explicit_mandatory_contradiction"
    elif shared_tasks and shared_skills:
        label, reason = "1", "shared_task_and_content_skill"
        has_detected_task = any(s["state"] == "task_detected" for s in jd["task_segments"])
        tasks_accounted = has_detected_task and all(
            s["state"] in {"task_detected", "support_context"} and s["bounded_statement_complete"]
            for s in jd["task_segments"]
        )
        if (tasks_accounted and set(jd["functions"]) <= set(cv["functions"])
                and jd["requirement_coverage"]["complete_bounded_grammar"]
                and mandatory and not unresolved and all(c["state"] == "yes" for c in mandatory + durations)):
            label, reason = "2", "supported_bounded_tasks_and_requirements"
    return dict(
        relevance_0_1_2=label,
        label_status="automatic_rule_proxy" if label else "insufficient_evidence",
        reason=reason,
        shared_functions=shared_tasks,
        shared_skills=shared_skills,
        mandatory_states=mandatory,
        duration_states=durations,
        unresolved_clause_indices=unresolved,
        title_used_for_decision=False,
        unseen_title_rejected=False,
        requirement_coverage_complete=jd["requirement_coverage"]["complete_bounded_grammar"],
        version=VERSION,
    )


def inspect_pair(payload):
    require(isinstance(payload.get("cv"), dict) and isinstance(payload.get("jd"), dict), "Expected cv and jd objects")
    cv_input, jd_input = payload["cv"], payload["jd"]
    require(isinstance(cv_input.get("text"), str) and bool(cv_input["text"].strip()), "CV text required")
    for field in ("tasks_text", "requirements_text", "preferred_requirements_text"):
        require(isinstance(jd_input.get(field, ""), str), "JD field must be text")
    cv = cv_facts(cv_input["text"], role=cv_input.get("role", ""))
    jd = job_facts(dict(occurrences=[dict(raw_row=jd_input)]))
    return dict(
        decision=judge(cv, jd),
        cv_facts=cv,
        jd_facts=jd,
        mode="offline_rule_diagnostic_not_trained_model_or_app",
        model_trained=False,
    )
