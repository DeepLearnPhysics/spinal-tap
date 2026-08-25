"""Tests for the Flask application factory and command-line entry point."""

import hashlib
from types import SimpleNamespace

import pytest
from flask import Flask

from spinal_tap import app as app_module
from spinal_tap import cache as cache_module


class UploadManager:
    """Small configurable upload manager used by the route tests."""

    max_chunk_bytes = 4

    def __init__(self):
        self.error = None
        self.calls = []

    def _result(self, name, *args):
        self.calls.append((name, args))
        if self.error:
            raise self.error
        return {"operation": name}

    def begin_upload(self, *args):
        return self._result("begin", *args)

    def write_chunk(self, *args):
        return self._result("write", *args)

    def finish_upload(self, *args):
        return self._result("finish", *args)

    def cancel_upload(self, *args):
        self._result("cancel", *args)


@pytest.fixture
def authenticated_client(monkeypatch):
    """Create an authenticated client backed by a configurable manager."""
    manager = UploadManager()
    monkeypatch.setattr(cache_module, "cache_manager", manager)
    monkeypatch.setattr(app_module, "REQUIRE_AUTH", True)
    dash_app = app_module.create_app(Flask(__name__))
    client = dash_app.server.test_client()
    with client.session_transaction() as user_session:
        user_session["authenticated"] = True
        user_session["experiment"] = "dune"
    return client, manager


def test_password_and_session_helpers(monkeypatch):
    """Authentication helpers should cover disabled, missing and valid states."""
    monkeypatch.setattr(app_module, "REQUIRE_AUTH", False)
    assert app_module.hash_password("secret") == hashlib.sha256(b"secret").hexdigest()
    assert app_module.check_password("dune", "anything")
    assert app_module.is_authenticated()
    assert app_module.get_experiment() is None

    monkeypatch.setattr(app_module, "REQUIRE_AUTH", True)
    monkeypatch.setattr(
        app_module,
        "EXPERIMENT_PASSWORDS",
        {"dune": app_module.hash_password("secret"), "sbnd": ""},
    )
    assert app_module.check_password("dune", "secret")
    assert not app_module.check_password("dune", "wrong")
    assert not app_module.check_password("sbnd", "secret")
    assert not app_module.is_authenticated()
    assert app_module.get_experiment() is None

    server = Flask(__name__)
    server.secret_key = "test"
    with server.test_request_context("/"):
        assert not app_module.is_authenticated()
        assert app_module.get_experiment() is None
        app_module.session["authenticated"] = True
        app_module.session["experiment"] = "dune"
        assert app_module.is_authenticated()
        assert app_module.get_experiment() == "dune"


def test_login_logout_and_scene_routes(monkeypatch):
    """The application factory should expose authentication lifecycle routes."""
    monkeypatch.setattr(app_module, "REQUIRE_AUTH", True)
    monkeypatch.setattr(
        app_module,
        "EXPERIMENT_PASSWORDS",
        {"dune": app_module.hash_password("secret")},
    )
    dash_app = app_module.create_app(Flask(__name__))
    client = dash_app.server.test_client()

    assert (
        client.post(
            "/login", data={"experiment": "dune", "password": "wrong"}
        ).status_code
        == 401
    )
    response = client.post("/login", data={"experiment": "dune", "password": "secret"})
    assert response.status_code == 302
    with client.session_transaction() as user_session:
        assert user_session["authenticated"] is True
    assert client.get("/logout").status_code == 302
    with client.session_transaction() as user_session:
        assert not user_session


def test_upload_routes_require_authentication(monkeypatch):
    """Every mutation endpoint should reject anonymous authenticated-mode users."""
    monkeypatch.setattr(app_module, "REQUIRE_AUTH", True)
    dash_app = app_module.create_app(Flask(__name__))
    client = dash_app.server.test_client()

    assert client.post("/api/uploads", json={}).status_code == 401
    assert client.put("/api/uploads/id/0", data=b"a").status_code == 401
    assert client.post("/api/uploads/id/complete").status_code == 401
    assert client.delete("/api/uploads/id").status_code == 401


@pytest.mark.parametrize(
    "error,status",
    [(PermissionError("disabled"), 403), (ValueError("bad size"), 400)],
)
def test_begin_upload_reports_manager_errors(authenticated_client, error, status):
    """Upload allocation errors should be returned as stable JSON responses."""
    client, manager = authenticated_client
    manager.error = error
    response = client.post("/api/uploads", json={"name": "a.h5", "size": 3})
    assert response.status_code == status
    assert response.get_json()["error"] == str(error)


def test_upload_route_success_and_validation(authenticated_client):
    """Chunk routes should validate request size and forward authenticated data."""
    client, manager = authenticated_client
    response = client.post("/api/uploads", json={"name": "a.h5", "size": 3})
    assert response.status_code == 201
    assert manager.calls[-1] == ("begin", ("a.h5", 3))

    assert client.put("/api/uploads/id/0").status_code == 413
    assert client.put("/api/uploads/id/0", data=b"12345").status_code == 413
    response = client.put(
        "/api/uploads/id/0",
        data=b"1234",
        headers={"X-Upload-Token": "token"},
    )
    assert response.status_code == 200
    assert manager.calls[-1] == ("write", ("id", "token", 0, b"1234"))

    response = client.post(
        "/api/uploads/id/complete", headers={"X-Upload-Token": "token"}
    )
    assert response.status_code == 200
    assert manager.calls[-1] == ("finish", ("id", "token"))
    response = client.delete("/api/uploads/id", headers={"X-Upload-Token": "token"})
    assert response.status_code == 204
    assert manager.calls[-1] == ("cancel", ("id", "token"))


@pytest.mark.parametrize(
    "method,url,error,status",
    [
        ("put", "/api/uploads/id/0", PermissionError("denied"), 403),
        ("put", "/api/uploads/id/0", ValueError("bad chunk"), 400),
        ("post", "/api/uploads/id/complete", PermissionError("denied"), 403),
        ("post", "/api/uploads/id/complete", ValueError("bad file"), 400),
        ("delete", "/api/uploads/id", PermissionError("denied"), 403),
    ],
)
def test_upload_mutation_errors(authenticated_client, method, url, error, status):
    """Chunk, completion and cancellation failures should stay user-visible."""
    client, manager = authenticated_client
    manager.error = error
    kwargs = {"headers": {"X-Upload-Token": "token"}}
    if method == "put":
        kwargs["data"] = b"1234"
    response = getattr(client, method)(url, **kwargs)
    assert response.status_code == status
    assert response.get_json()["error"] == str(error)


def test_main_version_debug_and_production(monkeypatch, capsys):
    """The CLI should support version, debug and quiet production startup."""
    monkeypatch.setattr("sys.argv", ["spinal-tap", "--version"])
    app_module.main()
    assert "Spinal Tap version" in capsys.readouterr().out

    calls = []
    fake_app = SimpleNamespace(
        server=object(),
        run=lambda **kwargs: calls.append(("debug", kwargs)),
    )
    monkeypatch.setattr(app_module, "create_app", lambda: fake_app)
    monkeypatch.setattr("sys.argv", ["spinal-tap", "--debug", "--port", "9000"])
    app_module.main()
    assert calls == [("debug", {"host": "0.0.0.0", "port": 9000, "debug": True})]

    monkeypatch.setattr(
        app_module,
        "run_simple",
        lambda host, port, server, threaded: calls.append(
            ("production", host, port, server, threaded)
        ),
    )
    monkeypatch.setattr("sys.argv", ["spinal-tap", "--host", "127.0.0.1"])
    app_module.main()
    assert calls[-1] == ("production", "127.0.0.1", 8888, fake_app.server, True)
    assert "http://127.0.0.1:8888/" in capsys.readouterr().out
