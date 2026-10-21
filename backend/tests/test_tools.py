import pytest
import os
import sys

# Ajout du chemin backend au PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.tools.web_search import search_web
from app.tools.weather import get_weather
from app.tools.calendar_tool import list_events, search_events, create_event
from app.tools.email_tool import prepare_email_draft
from app.tools.notion_tool import search_notion, read_notion_page
from app.tools.drive_tool import search_drive_files, read_drive_file_content
from app.tools.osint_tools import recon_social_profile, cti_threat_lookup, hunt_opportunities
from app.tools.rag_engine import query_local_knowledge

# Test 1 : Recherche Web (avec repli DuckDuckGo)
def test_search_web():
    res = search_web("cybersécurité intelligence artificielle 2026", max_results=3)
    assert res["status"] in ["success", "warning"]
    assert "results" in res
    assert len(res["results"]) > 0
    assert "sources" in res

# Test 2 : Météo (avec repli Open-Meteo sans clé)
def test_weather_single_and_multi():
    res_single = get_weather("Lomé")
    assert res_single["status"] == "success"
    assert res_single["type"] == "single_city"
    assert "temperature_c" in res_single["data"]

    res_multi = get_weather("Lomé, Accra")
    assert res_multi["status"] == "success"
    assert res_multi["type"] == "multi_city_comparison"
    assert len(res_multi["comparison"]) >= 2

# Test 3 : Google Calendar
def test_calendar():
    events = list_events(max_results=5)
    assert events["status"] == "success"
    assert "events" in events
    assert len(events["events"]) > 0

    # Création d'événement
    created = create_event(
        summary="Test Meeting Agent",
        start_time="2026-10-25T10:00:00Z",
        description="Test unitaire X-Finder"
    )
    assert created["status"] == "success"

# Test 4 : Email Draft & Confirmation de Sécurité
def test_email_draft_requires_confirmation():
    draft = prepare_email_draft(
        to_email="professeur@universite.fr",
        subject="Rapport d'avancement Assignment",
        body="Bonjour professeur, voici les résultats de mes tests sur l'agent X-Finder."
    )
    assert draft["status"] == "draft_ready"
    assert draft["requires_confirmation"] is True
    assert draft["confirmation_action"] == "send_email"
    assert draft["draft"]["to"] == "professeur@universite.fr"

# Test 5 : Notion API & Notes
def test_notion_search_and_read():
    search_res = search_notion("Machine Learning")
    assert search_res["status"] == "success"
    assert len(search_res["results"]) > 0

    page_id = search_res["results"][0]["id"]
    page_content = read_notion_page(page_id)
    assert page_content["status"] == "success"
    assert "Machine Learning" in page_content["title"]

# Test 6 : Google Drive API & Recherche de documents
def test_drive_search_and_read():
    search_res = search_drive_files("Proposition")
    assert search_res["status"] == "success"
    assert len(search_res["files"]) > 0

    doc_id = search_res["files"][0]["id"]
    doc_content = read_drive_file_content(doc_id)
    assert doc_content["status"] == "success"
    assert "X-Finder" in doc_content["content"]

# Test 7 : Reconnaissance OSINT & CTI
def test_osint_tools():
    threat = cti_threat_lookup("CVE-2024-3094")
    assert threat["status"] == "success"
    assert "findings_count" in threat

    opps = hunt_opportunities(opportunity_type="ctf", domain="cyber", location="Remote")
    assert opps["status"] == "success"
    assert "opportunities" in opps

# Test 8 : RAG Local
def test_rag_query():
    rag_res = query_local_knowledge("MITRE ATT&CK IOC")
    assert rag_res["status"] == "success"
    assert rag_res["matches_count"] > 0
