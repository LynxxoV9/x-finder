import os
import json
import base64
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database.db import get_db, init_db
from app.database.models import Conversation, Message, ToolExecution, PendingConfirmation
from app.agent.core import run_agent_turn
from app.agent.registry import TOOL_DEFINITIONS, FUNCTION_MAP
from app.tools.email_tool import send_email_confirmed, smtp_status
from app.tools.calendar_tool import delete_event
from app.tools.web_search import _is_usable_tavily_key

# Initialisation de la base de données
init_db()

app = FastAPI(
    title="X-Finder AI Agent API",
    description="Agent IA autonome avec Tool Calling, spécialisé en OSINT, CTI et Productivité.",
    version="1.0.0"
)

# Configuration CORS pour autoriser l'accès depuis n'importe quelle interface
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modèles Pydantic pour les requêtes
class ChatRequest(BaseModel):
    conversation_id: Optional[int] = None
    message: str
    model: Optional[str] = None
    image_base64: Optional[str] = None

class ConfirmationResponse(BaseModel):
    confirmed: bool # True pour valider l'action sensible, False pour annuler

class NewConversationRequest(BaseModel):
    title: Optional[str] = "Nouvelle mission X-Finder"
    model: Optional[str] = None


def _load_json(value: Optional[str], fallback: Any = None) -> Any:
    if value is None:
        return fallback
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return fallback


# 1. Routes de gestion des conversations
@app.post("/api/conversations")
def create_conversation(req: NewConversationRequest, db: Session = Depends(get_db)):
    """Crée une nouvelle session de conversation."""
    conv = Conversation(
        title=req.title,
        model_used=req.model or settings.DEFAULT_MODEL
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return {"status": "success", "conversation": {"id": conv.id, "title": conv.title, "model": conv.model_used}}


@app.get("/api/conversations")
def list_conversations(db: Session = Depends(get_db)):
    """Récupère l'historique de toutes les missions/conversations."""
    convs = db.query(Conversation).order_by(Conversation.updated_at.desc()).all()
    return {
        "conversations": [
            {
                "id": c.id,
                "title": c.title,
                "model": c.model_used,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None
            }
            for c in convs
        ]
    }


@app.get("/api/conversations/{conversation_id}")
def get_conversation_details(conversation_id: int, db: Session = Depends(get_db)):
    """Renvoie les messages, outils exécutés et confirmations d'une conversation."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation introuvable.")

    messages = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.id).all()
    tools = db.query(ToolExecution).filter(ToolExecution.conversation_id == conversation_id).order_by(ToolExecution.id).all()
    pending = db.query(PendingConfirmation).filter(
        PendingConfirmation.conversation_id == conversation_id,
        PendingConfirmation.status == "pending"
    ).all()

    return {
        "conversation": {
            "id": conv.id,
            "title": conv.title,
            "model": conv.model_used,
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "tool_calls": _load_json(m.tool_calls),
                    "tool_call_id": m.tool_call_id,
                    "name": m.name,
                    "image_url": m.image_url,
                    "created_at": m.created_at.isoformat() if m.created_at else None
                }
                for m in messages
            ],
            "executed_tools": [
                {
                    "id": t.id,
                    "tool_name": t.tool_name,
                    "arguments": _load_json(t.input_arguments, t.input_arguments or {}),
                    "output": _load_json(t.output_result, t.output_result),
                    "status": t.status,
                    "execution_time_ms": t.execution_time_ms
                }
                for t in tools
            ],
            "pending_confirmations": [
                {
                    "id": p.id,
                    "action_type": p.action_type,
                    "description": p.description,
                    "payload": _load_json(p.payload, p.payload or {})
                }
                for p in pending
            ]
        }
    }


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """Supprime une conversation et toutes ses données associées."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation introuvable.")
    db.delete(conv)
    db.commit()
    return {"status": "success", "message": "Conversation supprimée."}


# 2. Endpoint de discussion principal (Tool Calling Agent)
@app.post("/api/chat")
async def chat_with_agent(req: ChatRequest, db: Session = Depends(get_db)):
    """
    Envoie un message à l'agent X-Finder.
    Déclenche la sélection dynamique d'outils, la boucle de raisonnement et retourne la réponse consolidée.
    """
    conv_id = req.conversation_id
    if not conv_id:
        # Création automatique de la conversation avec titre dérivé du premier message
        preview = req.message[:45] + ("..." if len(req.message) > 45 else "")
        new_conv = Conversation(title=preview or "Mission X-Finder", model_used=req.model or settings.DEFAULT_MODEL)
        db.add(new_conv)
        db.commit()
        db.refresh(new_conv)
        conv_id = new_conv.id

    result = await run_agent_turn(
        conversation_id=conv_id,
        user_prompt=req.message,
        db=db,
        model=req.model,
        image_base64=req.image_base64
    )
    return result


# 3. Validation ou rejet d'une action sensible nécessitant confirmation
@app.post("/api/confirmations/{confirmation_id}/respond")
def respond_to_confirmation(confirmation_id: int, req: ConfirmationResponse, db: Session = Depends(get_db)):
    """
    Traite la décision de l'utilisateur pour une action protégée (ex: envoi d'email réel, suppression).
    """
    conf = db.query(PendingConfirmation).filter(PendingConfirmation.id == confirmation_id).first()
    if not conf:
        raise HTTPException(status_code=404, detail="Demande de confirmation introuvable.")

    if conf.status != "pending":
        return {"status": "already_processed", "message": f"Action déjà traitée ({conf.status})."}

    payload = _load_json(conf.payload, {})
    if not isinstance(payload, dict):
        raise HTTPException(status_code=500, detail="La demande de confirmation contient des données invalides.")

    if not req.confirmed:
        conf.status = "rejected"
        db.commit()
        # Message d'information système
        msg = Message(
            conversation_id=conf.conversation_id,
            role="assistant",
            content=f"Action '{conf.action_type}' annulée à votre demande."
        )
        db.add(msg)
        db.commit()
        return {"status": "rejected", "message": "Action annulée."}

    # Confirmation accordée : exécution de l'action
    action_result = {}
    if conf.action_type == "send_email":
        action_result = send_email_confirmed(
            to_email=payload.get("to"),
            subject=payload.get("subject"),
            body=payload.get("body")
        )
    elif conf.action_type == "delete_calendar_event":
        action_result = delete_event(event_id=payload.get("event_id"))
    else:
        action_result = {"status": "success", "message": f"Action {conf.action_type} exécutée."}

    conf.status = "confirmed" if action_result.get("status") in ("success", "warning") else "failed"

    result_status = action_result.get("status", "success")
    prefix = "Action exécutée" if result_status == "success" else (
        "Action traitée avec avertissement" if result_status == "warning" else "Échec de l'action"
    )
    msg = Message(
        conversation_id=conf.conversation_id,
        role="assistant",
        content=f"**{prefix} :**\n{action_result.get('message', 'Opération terminée.')}",
    )
    db.add(msg)
    db.commit()

    return {"status": conf.status, "result": action_result}


# 4. Upload de fichier image pour reconnaissance multimodale OSINT
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Retourne une image téléversée en mémoire, sans dépendre d'un disque persistant."""
    filename = Path(file.filename or "upload").name
    content = await file.read()
    base64_data = base64.b64encode(content).decode("utf-8")
    content_type = file.content_type or "image/png"
    data_url = f"data:{content_type};base64,{base64_data}"

    return {
        "status": "success",
        "filename": filename,
        "path": None,
        "data_url": data_url
    }


# 5. Liste des outils disponibles et métadonnées
@app.get("/api/tools")
def list_available_tools():
    """Retourne l'inventaire complet des outils connectés à l'agent."""
    return {
        "agent": "X-Finder Elite Agent",
        "total_tools": len(TOOL_DEFINITIONS),
        "tools": [
            {
                "name": t["function"]["name"],
                "description": t["function"]["description"],
                "parameters": t["function"]["parameters"]
            }
            for t in TOOL_DEFINITIONS
        ]
    }


# 6. État de santé et configuration
@app.get("/api/health")
def health_check():
    """Vérifie le bon fonctionnement du serveur et des intégrations."""
    smtp = smtp_status()
    return {
        "status": "healthy",
        "agent_name": "X-Finder",
        "llm_provider": "RodiumAI",
        "default_model": settings.DEFAULT_MODEL,
        "available_models": [m.strip() for m in settings.ALLOWED_MODELS.split(",") if m.strip()],
        "integrations": {
            "tavily": _is_usable_tavily_key(settings.TAVILY_API_KEY),
            "smtp": smtp,
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


# 7. Distribution des fichiers statiques du Frontend si compilé
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="static")
