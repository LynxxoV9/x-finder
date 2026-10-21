import os
import base64
from pathlib import Path
from typing import Dict, Any, Optional
import httpx
from PIL import Image
from PIL.ExifTags import TAGS
from app.config import settings

def analyze_image_intel(image_path_or_base64: str, task: str = "general_osint") -> Dict[str, Any]:
    """
    Analyse visuelle et multimodale d'une image pour la reconnaissance OSINT / CTI :
    - Extraction du texte visible (OCR)
    - Identification de marques, infrastructures, captures d'écran techniques
    - Extraction des métadonnées EXIF (date, coordonnées GPS, appareil)
    - Synthèse via le modèle de vision de RodiumAI
    """
    exif_data = {}
    base64_str = ""
    mime_type = "image/png"

    # Vérification si c'est un chemin de fichier local
    file_path = Path(image_path_or_base64)
    if file_path.exists() and file_path.is_file():
        try:
            # Extraction des métadonnées EXIF avec Pillow
            with Image.open(file_path) as img:
                info = img._getexif()
                if info:
                    for tag_id, value in info.items():
                        tag_name = TAGS.get(tag_id, tag_id)
                        # Conversion des types non sérialisables
                        exif_data[str(tag_name)] = str(value)[:100]

            with open(file_path, "rb") as f:
                raw_bytes = f.read()
                base64_str = base64.b64encode(raw_bytes).decode("utf-8")
                
            suffix = file_path.suffix.lower()
            if suffix in [".jpg", ".jpeg"]:
                mime_type = "image/jpeg"
            elif suffix == ".webp":
                mime_type = "image/webp"
            else:
                mime_type = "image/png"
        except Exception as e:
            return {"status": "error", "message": f"Erreur lecture image : {str(e)}"}
    elif "base64," in image_path_or_base64:
        # Chaîne Data URL
        parts = image_path_or_base64.split("base64,")
        base64_str = parts[1]
        if "data:image/jpeg" in parts[0]:
            mime_type = "image/jpeg"
    else:
        # Base64 brut
        base64_str = image_path_or_base64

    # Interrogation du modèle multimodal RodiumAI
    vision_prompt = (
        f"Tu es l'analyste d'images OSINT de l'agent X-Finder. Tâche : {task}.\n"
        "1. Décris précisément les éléments visuels clés (infrastructures, logos, visages floutés, schémas).\n"
        "2. Transcris tout le texte lisible (OCR) ou les commandes/erreurs affichées.\n"
        "3. Fournis une analyse de renseignement (indices de localisation, contexte technique, alertes éventuelles)."
    )

    payload = {
        "model": "google/gemini-2.5-flash-lite",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": vision_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_str}"
                        }
                    }
                ]
            }
        ],
        "temperature": 0.2
    }

    headers = {
        "Authorization": f"Bearer {settings.RODIUMAI_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            res = client.post(f"{settings.BASE_URL}/chat/completions", headers=headers, json=payload)
            if res.status_code == 200:
                ai_description = res.json()["choices"][0]["message"]["content"]
                return {
                    "status": "success",
                    "source": "RodiumAI Vision Analysis",
                    "exif_metadata": exif_data,
                    "visual_intelligence": ai_description,
                    "task": task
                }
            else:
                return {
                    "status": "warning",
                    "exif_metadata": exif_data,
                    "message": f"Analyse IA non disponible ({res.status_code}). Métadonnées EXIF extraites.",
                    "details": res.text[:200]
                }
    except Exception as e:
        return {
            "status": "error",
            "exif_metadata": exif_data,
            "message": f"Erreur lors de l'appel multimodal : {str(e)}"
        }
