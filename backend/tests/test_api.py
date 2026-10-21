import pytest
import os
import sys
from fastapi.testclient import TestClient

# Ajout du chemin backend au PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app

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
