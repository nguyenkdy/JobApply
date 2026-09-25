"""Run from repository root: python scripts/migrate.py [account|job|application|all]."""

import sys
from pathlib import Path
from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def migrate(service):
    config = Config(str(ROOT / "services" / service / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "services" / service / "migrations"))
    command.upgrade(config, "head")


if __name__ == "__main__":
    selected = sys.argv[1] if len(sys.argv) > 1 else "all"
    if selected not in ("all", "account", "job", "application"):
        raise SystemExit("Choose account, job, application or all")
    for name in ("account", "job", "application") if selected == "all" else (selected,):
        migrate(name)
