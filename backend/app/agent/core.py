import asyncio
import json
import time
from typing import Dict, Any, List, Optional
import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.agent.prompts import SYSTEM_PROMPT, TOOL_GROUNDING_REMINDER
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
    final_status = "success"
    assistant_response_saved = False

    headers = {
        "Authorization": f"Bearer {settings.RODIUMAI_API_KEY}",
        "Content-Type": "application/json"
    }

    loop_count = 0
    async with httpx.AsyncClient(timeout=90.0) as client:
        while loop_count < MAX_AGENT_LOOPS:
            loop_count += 1

            payload = {
                "model": selected_model,
                "messages": llm_messages,
                "tools": TOOL_DEFINITIONS,
                "tool_choice": "auto",
                "temperature": 0
            }

            try:
                res = await client.post(
                    f"{settings.BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload
                )
            except httpx.TimeoutException:
                final_text_content = "Le service LLM n'a pas répondu dans le délai imparti. Réessayez dans quelques instants."
                final_status = "error"
                break
            except httpx.HTTPError as exc:
                final_text_content = f"Impossible de contacter le service LLM : {exc}"
                final_status = "error"
                break

            if res.status_code != 200:
                final_text_content = f"Erreur du service LLM ({res.status_code}) : {res.text[:200]}"
                final_status = "error"
                break

            try:
                response_data = res.json()
                choice = response_data["choices"][0]
                message_obj = choice["message"]
            except (ValueError, KeyError, IndexError, TypeError):
                final_text_content = "Le service LLM a renvoyé une réponse invalide."
                final_status = "error"
                break

            content = message_obj.get("content")
            tool_calls = message_obj.get("tool_calls")

            if not tool_calls:
                final_text_content = content if isinstance(content, str) else ""
                if not final_text_content:
                    final_text_content = "Le modèle n'a fourni aucune réponse."
                    final_status = "error"
                assistant_msg_db = Message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=final_text_content
                )
                db.add(assistant_msg_db)
                db.commit()
                assistant_response_saved = True
                break

            assistant_mid_db = Message(
                conversation_id=conversation_id,
                role="assistant",
                content=content if isinstance(content, str) else None,
                tool_calls=json.dumps(tool_calls)
            )
            db.add(assistant_mid_db)
            db.commit()

            llm_messages.append({
                "role": "assistant",
                "content": content,
                "tool_calls": tool_calls
            })

            for tc in tool_calls:
                func_info = tc.get("function", {})
                call_id = tc.get("id")
                tool_name = func_info.get("name")
                tool_args = func_info.get("arguments", "{}")

                start_time = time.monotonic()
                tool_output = await asyncio.to_thread(execute_tool_call, tool_name, tool_args)
                elapsed_ms = int((time.monotonic() - start_time) * 1000)

                output_str = json.dumps(tool_output, ensure_ascii=False)
                llm_tool_content = output_str + "\n\n" + TOOL_GROUNDING_REMINDER

                exec_log = ToolExecution(
                    conversation_id=conversation_id,
                    tool_name=tool_name,
                    input_arguments=tool_args,
                    output_result=output_str,
                    status="success" if tool_output.get("status") != "error" else "error",
                    execution_time_ms=elapsed_ms
                )
                db.add(exec_log)

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

                tool_msg_db = Message(
                    conversation_id=conversation_id,
                    role="tool",
                    tool_call_id=call_id,
                    name=tool_name,
                    content=output_str
                )
                db.add(tool_msg_db)
                db.commit()

                llm_messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": tool_name,
                    "content": llm_tool_content
                })

                executed_tools_summary.append({
                    "tool_name": tool_name,
                    "arguments": tool_args,
                    "status": tool_output.get("status", "success"),
                    "execution_time_ms": elapsed_ms
                })

    if not assistant_response_saved:
        if final_status == "success" and loop_count >= MAX_AGENT_LOOPS:
            final_text_content = "La limite d'étapes de l'agent a été atteinte avant la réponse finale."
            final_status = "incomplete"
        assistant_msg_db = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=final_text_content
        )
        db.add(assistant_msg_db)
        db.commit()

    return {
        "status": final_status,
        "conversation_id": conversation_id,
        "model": selected_model,
        "response": final_text_content,
        "executed_tools": executed_tools_summary,
        "pending_confirmation": pending_conf_obj
    }
