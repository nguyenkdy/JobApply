import importlib
import os
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def system(tmp_path_factory):
    folder = tmp_path_factory.mktemp("jobapply")
    os.environ["JWT_SECRET"] = "test-secret-unique-for-isolated-tests-only-12345"
    os.environ["CV_STORAGE_PATH"] = str(folder / "cvs")
    admin_url = os.environ.get("TEST_DATABASE_URL")
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT") if admin_url else None
    databases = []
    modules, clients = {}, {}
    for name in ("account", "job", "application"):
        if admin:
            dbname = f"test_{name}_{uuid4().hex[:10]}"
            with admin.connect() as connection:
                connection.execute(text(f'CREATE DATABASE "{dbname}"'))
            databases.append(dbname)
            url = admin.url.set(database=dbname).render_as_string(hide_password=False)
        else:
            url = f"sqlite:///{(folder / (name + '.db')).as_posix()}"
        os.environ[f"{name.upper()}_DATABASE_URL"] = url
        os.environ[f"{name.upper()}_SERVICE_URL"] = f"http://{name}.test"
        config = Config(str(ROOT / "services" / name / "alembic.ini"))
        config.set_main_option("script_location", str(ROOT / "services" / name / "migrations"))
        command.upgrade(config, "head")
        command.upgrade(config, "head")  # repeated migration must be safe
        modules[name] = importlib.import_module(f"services.{name}.main")
        clients[name] = TestClient(modules[name].app)
    yield {"clients": clients, "modules": modules, "postgres": bool(admin)}
    for client in clients.values():
        client.close()
    for module in modules.values():
        module.engine.dispose()
    if admin:
        with admin.connect() as connection:
            for dbname in databases:
                connection.execute(text(f'DROP DATABASE "{dbname}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture
def api(system, monkeypatch):
    original_client = httpx.Client

    def transport(request):
        service = request.url.host.split(".")[0]
        client = system["clients"][service]
        response = client.request(
            request.method, request.url.raw_path.decode(), headers=dict(request.headers), content=request.content
        )
        return httpx.Response(response.status_code, content=response.content, headers=response.headers)

    monkeypatch.setattr(
        httpx, "Client", lambda **kwargs: original_client(transport=httpx.MockTransport(transport), **kwargs)
    )
    return system["clients"]
