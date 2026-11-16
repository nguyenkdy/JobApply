"""Deterministic artifact I/O; all outputs are new directories."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import shutil
import unicodedata

from . import VERSION

ROOT = Path(__file__).resolve().parents[1]
MIN_PROFESSIONAL_BODY_CHARS = 80


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def write_lines(path, rows):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")


def read_lines(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


def csv_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames or []
        require(columns and all(c.strip() for c in columns) and len(columns) == len(set(columns)), "Invalid CSV header")
        rows = list(reader)
        require(all(None not in r and all(v is not None for v in r.values()) for r in rows), "Malformed CSV row")
        return columns, rows


def write_csv(path, rows, fields):
    with Path(path).open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def normalize(text):
    """NFKC and whitespace only: no invented sections, skills or durations."""
    return "\n".join(" ".join(line.split()) for line in unicodedata.normalize("NFKC", text).splitlines() if line.strip())


def fresh_folder(output, protected=()):
    output = Path(output).resolve()
    protected = (*protected, ROOT / "jobapply_pilot_v1", ROOT / ".git")
    require(not any(output.is_relative_to(Path(p).resolve()) for p in protected), "Output is inside a protected input/pilot directory")
    output.mkdir(parents=True, exist_ok=False)
    return output


def seal(folder, artifact_type, metadata):
    source = folder / "tool_source"
    source.mkdir()
    for path in sorted(Path(__file__).parent.glob("*.py")):
        shutil.copyfile(path, source / path.name)
    manifest = dict(version=VERSION, artifact_type=artifact_type, **metadata,
                    artifacts={p.relative_to(folder).as_posix(): file_hash(p)
                               for p in sorted(folder.rglob("*")) if p.is_file()})
    write_json(folder / "manifest.json", manifest)
    return manifest


def verify(folder, artifact_type=None):
    folder = Path(folder).resolve()
    manifest = read_json(folder / "manifest.json")
    require(manifest.get("version") == VERSION, "Unsupported data artifact version")
    if artifact_type:
        require(manifest.get("artifact_type") == artifact_type, "Wrong artifact type")
    for name, expected in manifest["artifacts"].items():
        path = (folder / name).resolve()
        require(path.is_relative_to(folder) and file_hash(path) == expected, f"Artifact integrity failure: {name}")
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}
    require(actual == set(manifest["artifacts"]) | {"manifest.json"}, "Unmanifested/missing files")
    return manifest


def distribution(records):
    result = {}
    for kind in ("cv", "jd"):
        rows = [r for r in records if r["kind"] == kind]
        result[kind] = dict(total=len(rows), decisions=dict(Counter(r["decision"] for r in rows)),
                            roles=dict(Counter(r["role"] or "unknown" for r in rows)),
                            synthetic=dict(Counter(str(r["is_synthetic"]) for r in rows)),
                            missing=dict(Counter(k for r in rows for k in r["missing_fields"])))
    return result
