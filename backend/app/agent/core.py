import json
import time
from typing import Dict, Any, List, Optional, AsyncGenerator
import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.registry import TOOL_DEFINITIONS, execute_tool_call
from app.database.models import Message, ToolExecution, PendingConfirmation

# Coeur de l'agent X-Finder : boucle de raisonnement et exécution dynamique des outils

MAX_AGENT_LOOPS = 8

async def run_agent_turn(
    conversation_id: int,
    user_prompt: str,
    db: Session,
    model: Optional[str] = None,
    image_base64: Optional[str] = None
) -> Dict[str, Any]:
    """
    Exécute un tour de conversation avec l'agent X-Finder.
    Prend en charge la sélection dynamique d'outils, le multi-tool chaining et les entrées multimodales.
    """
    selected_model = model or settings.DEFAULT_MODEL

    # 1. Récupération de l'historique de la conversation
    history_messages = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.id).all()

    # 2. Construction de la charge de messages pour le LLM
    llm_messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    for msg in history_messages:
        if msg.role == "user":
            if msg.image_url:
                llm_messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": msg.content or ""},
                        {"type": "image_url", "image_url": {"url": msg.image_url}}
                    ]
                })
            else:
                llm_messages.append({"role": "user", "content": msg.content or ""})
        elif msg.role == "assistant":
            msg_dict = {"role": "assistant", "content": msg.content}
            if msg.tool_calls:
                try:
                    msg_dict["tool_calls"] = json.loads(msg.tool_calls)
                except Exception:
                    pass
            llm_messages.append(msg_dict)
        elif msg.role == "tool":
            llm_messages.append({
                "role": "tool",
                "tool_call_id": msg.tool_call_id or "",
                "name": msg.name or "",
                "content": msg.content or ""
            })

    # 3. Ajout du message utilisateur actuel
    user_msg_db = Message(
        conversation_id=conversation_id,
        role="user",
        content=user_prompt,
        image_url=image_base64
    )
    db.add(user_msg_db)
    db.commit()

    if image_base64:
        llm_messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": image_base64}}
            ]
        })
    else:
        llm_messages.append({"role": "user", "content": user_prompt})

    # 4. Boucle d'exécution dynamique des outils (Tool Calling Loop)
    executed_tools_summary = []
    pending_conf_obj = None
    final_text_content = ""

    headers = {
        "Authorization": f"Bearer {settings.RODIUMAI_API_KEY}",
        "Content-Type": "application/json"
    }

    loop_count = 0
    while loop_count < MAX_AGENT_LOOPS:
        loop_count += 1

        payload = {
            "model": selected_model,
            "messages": llm_messages,
            "tools": TOOL_DEFINITIONS,
            "tool_choice": "auto",
            "temperature": 0.3
        }

        # Appel au fournisseur LLM (RodiumAI / OpenAI compatible)
        async with httpx.AsyncClient(timeout=45.0) as client:
            res = await client.post(f"{settings.BASE_URL}/chat/completions", headers=headers, json=payload)
            if res.status_code != 200:
                error_msg = f"Erreur du service LLM ({res.status_code}) : {res.text[:200]}"
                final_text_content = error_msg
                break

            response_data = res.json()
            choice = response_data.get("choices", [{}])[0]
            message_obj = choice.get("message", {})

            content = message_obj.get("content")
            tool_calls = message_obj.get("tool_calls")

            # Cas A : Le modèle n'a pas appelé d'outils supplémentaires et termine sa réponse
            if not tool_calls:
                final_text_content = content or ""
                # Sauvegarde du message assistant final en base
                assistant_msg_db = Message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=final_text_content
                )
                db.add(assistant_msg_db)
                db.commit()
                break

            # Cas B : Le modèle a sélectionné un ou plusieurs outils à exécuter
            # Enregistrement du message assistant intermédiaire avec tool_calls
            assistant_mid_db = Message(
                conversation_id=conversation_id,
                role="assistant",
                content=content,
                tool_calls=json.dumps(tool_calls)
            )
            db.add(assistant_mid_db)
            db.commit()

            # Ajout à l'historique en mémoire pour la prochaine itération
            llm_messages.append({
                "role": "assistant",
                "content": content,
                "tool_calls": tool_calls
            })

            # Exécution de chaque outil
            for tc in tool_calls:
                func_info = tc.get("function", {})
                call_id = tc.get("id")
                tool_name = func_info.get("name")
                tool_args = func_info.get("arguments", "{}")

                start_time = time.time()
                tool_output = execute_tool_call(tool_name, tool_args)
                elapsed_ms = int((time.time() - start_time) * 1000)

                output_str = json.dumps(tool_output, ensure_ascii=False)

                # Journalisation en base de données pour évaluation et audit
                exec_log = ToolExecution(
                    conversation_id=conversation_id,
                    tool_name=tool_name,
                    input_arguments=tool_args,
                    output_result=output_str[:3000], # Tronqué si très long
                    status="success" if tool_output.get("status") != "error" else "error",
                    execution_time_ms=elapsed_ms
                )
                db.add(exec_log)

                # Si l'action nécessite une confirmation explicite (ex: envoi d'email, suppression)
                if tool_output.get("requires_confirmation"):
                    conf = PendingConfirmation(
                        conversation_id=conversation_id,
                        action_type=tool_output.get("confirmation_action", "general_confirm"),
                        payload=json.dumps(tool_output.get("draft", {})),
                        description=tool_output.get("message", "Confirmation requise"),
                        status="pending"
                    )
                    db.add(conf)
                    db.commit()
                    db.refresh(conf)
                    pending_conf_obj = {
                        "id": conf.id,
                        "action_type": conf.action_type,
                        "description": conf.description,
                        "payload": json.loads(conf.payload) if conf.payload else {}
                    }

                # Enregistrement de la réponse d'outil dans la table messages
                tool_msg_db = Message(
                    conversation_id=conversation_id,
                    role="tool",
                    tool_call_id=call_id,
                    name=tool_name,
                    content=output_str
                )
                db.add(tool_msg_db)
                db.commit()

                # Ajout dans les messages transmis au LLM
                llm_messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": tool_name,
                    "content": output_str
                })

                executed_tools_summary.append({
                    "tool_name": tool_name,
                    "arguments": tool_args,
                    "status": tool_output.get("status", "success"),
                    "execution_time_ms": elapsed_ms
                })

    return {
        "status": "success",
        "conversation_id": conversation_id,
        "model": selected_model,
        "response": final_text_content,
        "executed_tools": executed_tools_summary,
        "pending_confirmation": pending_conf_obj
    }
