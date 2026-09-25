"""Local debug: defaults to PostgreSQL; --sqlite-smoke is isolated test-only mode."""

import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sqlite-smoke", action="store_true", help="Temporary local smoke databases; production always PostgreSQL"
    )
    args = parser.parse_args()
    os.chdir(ROOT)
    if (ROOT / ".env").exists():
        for line in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
    data = ROOT / ".test-data" / "smoke"
    if args.sqlite_smoke:
        data.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("JWT_SECRET", "isolated-local-smoke-secret-do-not-use-in-production")
    os.environ.setdefault("CV_STORAGE_PATH", str(data / "cvs"))
    for name, port in [("account", 8001), ("job", 8002), ("application", 8003)]:
        os.environ.setdefault(f"{name.upper()}_SERVICE_URL", f"http://127.0.0.1:{port}")
        if args.sqlite_smoke:
            os.environ[f"{name.upper()}_DATABASE_URL"] = f"sqlite:///{(data / (name + '.db')).as_posix()}"
        else:
            password = quote(os.environ[f"{name.upper()}_DB_PASSWORD"], safe="")
            os.environ.setdefault(
                f"{name.upper()}_DATABASE_URL", f"postgresql+psycopg://{name}_user:{password}@127.0.0.1:5432/{name}_db"
            )
    from scripts.migrate import migrate

    for name in ("account", "job", "application"):
        migrate(name)
    processes = []

    def stop(*args):
        for process in processes:
            process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        for name, port in [("account", 8001), ("job", 8002), ("application", 8003)]:
            processes.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        f"services.{name}.main:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(port),
                        "--no-access-log",
                    ]
                )
            )
        print("APIs: 127.0.0.1:8001 / 8002 / 8003. Run frontend separately. Ctrl+C stops all APIs.", flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(1)
    finally:
        stop()


if __name__ == "__main__":
    main()
