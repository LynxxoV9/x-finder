import pytest
import os
import sys
import asyncio
import json
import uuid
from urllib.parse import parse_qs, urlparse
from sqlalchemy import Text
from sqlalchemy.exc import OperationalError
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Ajout du chemin backend au PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.database.db import SessionLocal
from app.database.models import Message, ToolExecution
from app.auth import SESSION_COOKIE, get_current_user

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        response = test_client.post("/api/auth/register", json={
            "email": f"{uuid.uuid4().hex}@example.test",
            "password": "test-password-1234",
            "display_name": "Test user",
        })
        assert response.status_code == 200
        test_client.headers.update({"X-CSRF-Token": response.json()["csrf_token"]})
        yield test_client

def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["agent_name"] == "X-Finder"


def test_current_user_retries_after_database_disconnect():
    class FakeQuery:
        calls = 0

        def options(self, *args):
            return self

        def filter(self, *args):
            return self

        def first(self):
            self.calls += 1
            if self.calls == 1:
                raise OperationalError("SELECT", {}, Exception("connection closed"))
            return type("Session", (), {"user": object()})()

    class FakeDatabase:
        def __init__(self):
            self.query_result = FakeQuery()
            self.rollbacks = 0

        def query(self, model):
            return self.query_result

        def rollback(self):
            self.rollbacks += 1

    request = Request({
        "type": "http",
        "headers": [(b"cookie", f"{SESSION_COOKIE}=test-token".encode())],
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "server": ("test", 80),
        "client": ("test", 80),
        "scheme": "http",
    })
    db = FakeDatabase()

    get_current_user(request, db)

    assert db.query_result.calls == 2
    assert db.rollbacks == 1


def test_list_tools(client):
    response = client.get("/api/tools")
    assert response.status_code == 200
    data = response.json()
    assert data["total_tools"] >= 10
    tool_names = [t["name"] for t in data["tools"]]
    assert "search_web" in tool_names
    assert "get_weather" in tool_names
    assert "list_calendar_events" in tool_names
    assert "prepare_email_draft" in tool_names
    assert "send_email_confirmed" not in tool_names
    assert "search_notion" in tool_names
    assert "search_drive_files" in tool_names

def test_conversation_lifecycle(client):
    # 1. Création
    create_res = client.post("/api/conversations", json={"title": "Test Suite Conv"})
    assert create_res.status_code == 200
    conv = create_res.json()["conversation"]
    conv_id = conv["id"]

    # 2. Récupération
    detail_res = client.get(f"/api/conversations/{conv_id}")
    assert detail_res.status_code == 200

    # 3. Suppression
    del_res = client.delete(f"/api/conversations/{conv_id}")
    assert del_res.status_code == 200


def test_conversation_details_handles_truncated_tool_result(client):
    conv_id = client.post("/api/conversations", json={}).json()["conversation"]["id"]
    truncated_result = '{"findings":"' + ("x" * 3000)

    with SessionLocal() as db:
        db.add(Message(conversation_id=conv_id, role="assistant", tool_calls="[invalid"))
        db.add(ToolExecution(
            conversation_id=conv_id,
            tool_name="investigate_person_osint",
            input_arguments='{"full_name":"Example Person"}',
            output_result=truncated_result,
            status="success",
            execution_time_ms=10,
        ))
        db.commit()

    response = client.get(f"/api/conversations/{conv_id}")
    assert response.status_code == 200
    data = response.json()["conversation"]
    assert data["messages"][0]["tool_calls"] is None
    assert data["executed_tools"][0]["output"] == truncated_result

    assert client.delete(f"/api/conversations/{conv_id}").status_code == 200


def test_agent_persists_complete_tool_result(client, monkeypatch):
    from app.agent import core

    assert isinstance(Message.__table__.c.tool_call_id.type, Text)
    monkeypatch.setattr(core.settings, "RODIUMAI_API_KEY", "test-llm-key")
    conv_id = client.post("/api/conversations", json={}).json()["conversation"]["id"]
    large_result = {"status": "success", "results": ["x" * 4000]}
    responses = [
        {
            "choices": [{
                "message": {
                    "content": None,
                    "tool_calls": [{
                        "id": "call-" + ("x" * 400),
                        "function": {"name": "search_web", "arguments": '{"query":"test"}'},
                    }],
                }
            }]
        },
        {"choices": [{"message": {"content": "Recherche terminée.", "tool_calls": None}}]},
    ]

    class FakeResponse:
        status_code = 200
        text = ""

        def __init__(self, body):
            self.body = body

        def json(self):
            return self.body

    class FakeClient:
        def __init__(self, **kwargs):
            self.response_index = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            assert kwargs["headers"]["Authorization"] == "Bearer test-llm-key"
            body = responses[self.response_index]
            self.response_index += 1
            return FakeResponse(body)

    monkeypatch.setattr(core.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(core, "execute_tool_call", lambda *args: large_result)

    with SessionLocal() as db:
        result = asyncio.run(core.run_agent_turn(conv_id, "Recherche de test", db))
        execution = db.query(ToolExecution).filter(
            ToolExecution.conversation_id == conv_id
        ).one()
        assert result["status"] == "success"
        assert len(execution.output_result) > 3000
        assert execution.output_result == json.dumps(large_result, ensure_ascii=False)
        tool_message = db.query(Message).filter(
            Message.conversation_id == conv_id,
            Message.role == "tool",
        ).one()
        assert len(tool_message.tool_call_id) == 405

    details = client.get(f"/api/conversations/{conv_id}")
    assert details.status_code == 200
    assert details.json()["conversation"]["executed_tools"][0]["output"] == large_result
    assert client.delete(f"/api/conversations/{conv_id}").status_code == 200


def test_agent_persists_llm_provider_errors(client, monkeypatch):
    from app.agent import core

    monkeypatch.setattr(core.settings, "RODIUMAI_API_KEY", "test-llm-key")
    conv_id = client.post("/api/conversations", json={}).json()["conversation"]["id"]

    class FakeResponse:
        status_code = 429
        text = "Usage limit reached"

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(core.httpx, "AsyncClient", FakeClient)

    with SessionLocal() as db:
        result = asyncio.run(core.run_agent_turn(conv_id, "Recherche", db))
        assert result["status"] == "error"

    details = client.get(f"/api/conversations/{conv_id}")
    assert details.status_code == 200
    assert "429" in details.json()["conversation"]["messages"][-1]["content"]
    assert client.delete(f"/api/conversations/{conv_id}").status_code == 200


def test_agent_handles_llm_payment_required_402(client, monkeypatch):
    from app.agent import core

    monkeypatch.setattr(core.settings, "RODIUMAI_API_KEY", "test-llm-key")
    conv_id = client.post("/api/conversations", json={}).json()["conversation"]["id"]

    class FakeResponse:
        status_code = 402
        text = "Payment Required"

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(core.httpx, "AsyncClient", FakeClient)

    with SessionLocal() as db:
        result = asyncio.run(core.run_agent_turn(conv_id, "Bonjour", db))
        assert result["status"] == "error"
        assert "402" in result["response"]
        assert "Solde insuffisant" in result["response"]

    assert client.delete(f"/api/conversations/{conv_id}").status_code == 200


def test_agent_handles_llm_timeout(client, monkeypatch):
    import httpx
    from app.agent import core

    monkeypatch.setattr(core.settings, "RODIUMAI_API_KEY", "test-llm-key")
    conv_id = client.post("/api/conversations", json={}).json()["conversation"]["id"]

    class FakeTimeoutClient:
        def __init__(self, **kwargs):
            assert kwargs.get("timeout") == 35.0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            raise httpx.TimeoutException("Request timed out")

    monkeypatch.setattr(core.httpx, "AsyncClient", FakeTimeoutClient)

    with SessionLocal() as db:
        result = asyncio.run(core.run_agent_turn(conv_id, "Bonjour", db))
        assert result["status"] == "error"
        assert "35s" in result["response"]

    assert client.delete(f"/api/conversations/{conv_id}").status_code == 200


def test_agent_reports_missing_llm_key(client, monkeypatch):
    from app.agent import core

    monkeypatch.setattr(core.settings, "RODIUMAI_API_KEY", "")
    conversation_id = client.post("/api/conversations", json={}).json()["conversation"]["id"]
    with SessionLocal() as db:
        result = asyncio.run(core.run_agent_turn(conversation_id, "Bonjour", db))
    assert result["status"] == "error"
    assert "RODIUMAI_API_KEY" in result["response"]
    assert client.delete(f"/api/conversations/{conversation_id}").status_code == 200


def test_auth_requires_login_and_issues_revocable_session():
    with TestClient(app) as anonymous:
        assert anonymous.get("/api/conversations").status_code == 401
        response = anonymous.post("/api/auth/register", json={
            "email": f"{uuid.uuid4().hex}@example.test",
            "password": "a-strong-test-password",
        })
        assert response.status_code == 200
        assert response.headers["set-cookie"].startswith("xfinder_session=")
        assert anonymous.get("/api/auth/me").json()["csrf_token"] == response.json()["csrf_token"]

        assert anonymous.post("/api/conversations", json={}).status_code == 403
        anonymous.headers.update({"X-CSRF-Token": response.json()["csrf_token"]})
        created = anonymous.post("/api/conversations", json={})
        assert created.status_code == 200
        conversation_id = created.json()["conversation"]["id"]

        assert anonymous.post("/api/auth/logout").status_code == 200
        assert anonymous.get("/api/conversations").status_code == 401
        assert anonymous.get(f"/api/conversations/{conversation_id}").status_code == 401


def test_email_login_and_conversation_isolation(client):
    email = client.get("/api/auth/me").json()["email"]
    with TestClient(app) as second_user:
        registration = second_user.post("/api/auth/register", json={
            "email": f"{uuid.uuid4().hex}@example.test",
            "password": "another-strong-password",
        })
        second_user.headers.update({"X-CSRF-Token": registration.json()["csrf_token"]})
        conversation_id = client.post("/api/conversations", json={}).json()["conversation"]["id"]
        assert second_user.get(f"/api/conversations/{conversation_id}").status_code == 404

    with TestClient(app) as login_client:
        login = login_client.post("/api/auth/login", json={
            "email": email.upper(),
            "password": "test-password-1234",
        })
        assert login.status_code == 200
        assert login_client.get("/api/auth/me").json()["email"] == email
        assert login_client.post("/api/auth/login", json={
            "email": email,
            "password": "wrong-password",
        }).status_code == 401


def test_email_registration_rejects_weak_password():
    with TestClient(app) as anonymous:
        response = anonymous.post("/api/auth/register", json={
            "email": f"{uuid.uuid4().hex}@example.test",
            "password": "short",
        })
        assert response.status_code == 422


def test_user_can_update_and_clear_profile_name(client):
    assert client.get("/api/auth/me").json()["display_name"] == "Test user"

    updated = client.patch("/api/auth/me", json={"display_name": "  New Name  "})
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "New Name"
    assert client.get("/api/auth/me").json()["display_name"] == "New Name"

    cleared = client.patch("/api/auth/me", json={"display_name": ""})
    assert cleared.status_code == 200
    assert cleared.json()["display_name"] is None


def test_user_profile_update_requires_csrf():
    with TestClient(app) as profile_client:
        registered = profile_client.post("/api/auth/register", json={
            "email": f"{uuid.uuid4().hex}@example.test",
            "password": "test-password-1234",
            "display_name": "Test user",
        })
        assert registered.status_code == 200
        assert profile_client.patch(
            "/api/auth/me", json={"display_name": "Changed"}
        ).status_code == 403


def test_unconfigured_oauth_provider_is_not_advertised(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "")
    with TestClient(app) as anonymous:
        assert anonymous.get("/api/auth/providers").json()["google"] is False
        assert anonymous.get("/api/auth/google/login").status_code == 503


def test_google_oauth_uses_single_use_state_and_creates_session(monkeypatch):
    from app import auth
    from app.config import settings

    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-client")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://xfinder.example")

    async def exchange(provider, code, verifier, callback_url):
        assert provider == "google"
        assert code == "authorization-code"
        assert verifier
        assert callback_url == "https://xfinder.example/api/auth/google/callback"
        return "oauth-user@example.test", "google-subject-123", "OAuth User"

    monkeypatch.setattr(auth, "_exchange_code", exchange)
    with TestClient(app, follow_redirects=False) as oauth_client:
        start = oauth_client.get("/api/auth/google/login")
        assert start.status_code == 303
        query = parse_qs(urlparse(start.headers["location"]).query)
        state = query["state"][0]
        assert query["code_challenge_method"] == ["S256"]
        assert start.cookies.get("oauth_state_google") == state

        callback = oauth_client.get(
            "/api/auth/google/callback",
            params={"code": "authorization-code", "state": state},
        )
        assert callback.status_code == 303
        assert callback.headers["location"] == settings.FRONTEND_ORIGIN
        assert oauth_client.get("/api/auth/me").json()["email"] == "oauth-user@example.test"
        replay = oauth_client.get(
            "/api/auth/google/callback",
            params={"code": "authorization-code", "state": state},
        )
        assert replay.status_code == 400
