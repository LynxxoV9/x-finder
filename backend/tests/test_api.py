import pytest
import os
import sys
import asyncio
import json
from fastapi.testclient import TestClient

# Ajout du chemin backend au PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.database.db import SessionLocal
from app.database.models import Message, ToolExecution

client = TestClient(app)

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["agent_name"] == "X-Finder"

def test_list_tools():
    response = client.get("/api/tools")
    assert response.status_code == 200
    data = response.json()
    assert data["total_tools"] >= 10
    tool_names = [t["name"] for t in data["tools"]]
    assert "search_web" in tool_names
    assert "get_weather" in tool_names
    assert "list_calendar_events" in tool_names
    assert "prepare_email_draft" in tool_names
    assert "search_notion" in tool_names
    assert "search_drive_files" in tool_names

def test_conversation_lifecycle():
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


def test_conversation_details_handles_truncated_tool_result():
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


def test_agent_persists_complete_tool_result(monkeypatch):
    from app.agent import core

    conv_id = client.post("/api/conversations", json={}).json()["conversation"]["id"]
    large_result = {"status": "success", "results": ["x" * 4000]}
    responses = [
        {
            "choices": [{
                "message": {
                    "content": None,
                    "tool_calls": [{
                        "id": "call-1",
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

    details = client.get(f"/api/conversations/{conv_id}")
    assert details.status_code == 200
    assert details.json()["conversation"]["executed_tools"][0]["output"] == large_result
    assert client.delete(f"/api/conversations/{conv_id}").status_code == 200


def test_agent_persists_llm_provider_errors(monkeypatch):
    from app.agent import core

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
