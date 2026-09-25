"""Deployment invariants; static checks do not claim a Docker/VM deployment."""

from pathlib import Path
import io

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_only_gateway_is_exposed_to_vm_network():
    config = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    services = config["services"]
    assert [name for name, service in services.items() if "ports" in service] == ["frontend"]
    assert services["frontend"]["ports"] == ["${APP_BIND_ADDRESS:-0.0.0.0}:${APP_PORT:-8080}:80"]
    assert services["seed"]["profiles"] == ["tools"]
    assert services["tests"]["profiles"] == ["test"]
    assert set(config["volumes"]) == {"postgres_data", "cv_data"}
    for name in ("account", "job", "application"):
        environment = services[name]["environment"]
        database_keys = [key for key in environment if key.endswith("_DATABASE_URL")]
        assert database_keys == [f"{name.upper()}_DATABASE_URL"]
        assert environment["API_ROOT_PATH"] == f"/api/{name}"
        for peer in ("account", "job", "application"):
            assert environment[f"{peer.upper()}_SERVICE_URL"] == f"http://{peer}:8000"
        assert services[name]["healthcheck"]


def test_linux_scripts_use_lf_and_no_secrets_in_example():
    for path in [*ROOT.joinpath("scripts").glob("*.sh"), *ROOT.joinpath("infra").glob("*.sh")]:
        content = path.read_bytes()
        assert content.startswith(b"#!/bin/sh\n"), path
        assert b"\r\n" not in content, path
    lines = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    values = dict(line.split("=", 1) for line in lines if line and not line.startswith("#"))
    assert all(value.startswith("CHANGE_ME") for key, value in values.items() if "PASSWORD" in key or "SECRET" in key)


def test_gateway_routes_are_relative_and_no_http_login_redirect():
    nginx = (ROOT / "frontend/nginx.conf").read_text(encoding="utf-8")
    for service in ("account", "job", "application"):
        assert f"location /api/{service}/" in nginx
        assert f"proxy_pass http://{service}:8000/" in nginx
    source = (ROOT / "frontend/src/api.js").read_text(encoding="utf-8")
    assert "fetch(`/api${path}`" in source
    assert "localhost" not in source and "http://" not in source
    assert "return 301" not in nginx and "return 302" not in nginx


def test_migrations_compile_for_postgresql_without_connecting(monkeypatch):
    from alembic import command
    from alembic.config import Config

    for service in ("account", "job", "application"):
        monkeypatch.setenv(
            f"{service.upper()}_DATABASE_URL", "postgresql+psycopg://schema_check@localhost/schema_check"
        )
        output = io.StringIO()
        config = Config(str(ROOT / "services" / service / "alembic.ini"), output_buffer=output)
        config.set_main_option("script_location", str(ROOT / "services" / service / "migrations"))
        command.upgrade(config, "head", sql=True)
        sql = output.getvalue()
        assert "CREATE TABLE" in sql and "TIMESTAMP WITH TIME ZONE" in sql
        if service == "application":
            assert "uq_application_candidate_job UNIQUE (candidate_id, job_id)" in sql
