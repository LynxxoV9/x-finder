#!/usr/bin/env python3
# ==============================================================================
# X-Finder AI Agent - Lanceur Multi-Plateforme (Windows & Linux / macOS)
# Commande d'exécution : python run.py [--dev] [--port 8000]
# ==============================================================================

import os
import sys
import subprocess
import socket
import webbrowser
import time
import argparse
import hashlib
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"
VENV_DIR = BACKEND_DIR / "venv"
REQUIREMENTS_FILE = BACKEND_DIR / "requirements.txt"
REQUIREMENTS_MARKER = VENV_DIR / ".requirements.sha256"

# Détection de l'exécutable Python dans le venv
if sys.platform == "win32":
    VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
    VENV_PIP = VENV_DIR / "Scripts" / "pip.exe"
else:
    VENV_PYTHON = VENV_DIR / "bin" / "python"
    VENV_PIP = VENV_DIR / "bin" / "pip"


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Vérifie si un port réseau est déjà occupé."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex((host, port)) == 0


def ensure_backend_env():
    """Vérifie et configure l'environnement virtuel et les dépendances Python."""
    print("🔍 [1/3] Vérification de l'environnement Python...")
    created_venv = False
    if not VENV_PYTHON.exists():
        print(f"  Création de l'environnement virtuel dans {VENV_DIR}...")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])
        created_venv = True
    else:
        print("  Environnement virtuel Python prêt.")

    requirements_hash = hashlib.sha256(REQUIREMENTS_FILE.read_bytes()).hexdigest()
    installed_hash = REQUIREMENTS_MARKER.read_text(encoding="utf-8").strip() if REQUIREMENTS_MARKER.exists() else ""
    if installed_hash != requirements_hash:
        print("  Installation ou mise à jour des dépendances backend...")
        if created_venv:
            subprocess.check_call([str(VENV_PYTHON), "-m", "pip", "install", "--upgrade", "pip"])
        subprocess.check_call([
            str(VENV_PYTHON),
            "-m",
            "pip",
            "install",
            "-r",
            str(REQUIREMENTS_FILE),
        ])
        REQUIREMENTS_MARKER.write_text(requirements_hash + "\n", encoding="utf-8")
    else:
        print("  Dépendances backend à jour.")

    # Vérification du fichier .env
    env_file = ROOT_DIR / ".env"
    backend_env = BACKEND_DIR / ".env"
    if not env_file.exists() and not backend_env.exists():
        example_env = ROOT_DIR / ".env.example"
        if example_env.exists():
            print("  Création du fichier .env à partir de .env.example...")
            import shutil
            shutil.copy(example_env, env_file)
            shutil.copy(example_env, backend_env)


def ensure_frontend_built():
    """S'assure que le bundle frontend est compilé pour distribution FastAPI."""
    print("🔍 [2/3] Vérification du build Frontend...")
    dist_index = FRONTEND_DIR / "dist" / "index.html"
    if not dist_index.exists():
        print("  Le bundle frontend n'est pas encore compilé. Compilation en cours...")
        try:
            # Vérification de npm
            npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
            subprocess.check_call([npm_cmd, "install"], cwd=str(FRONTEND_DIR))
            subprocess.check_call([npm_cmd, "run", "build"], cwd=str(FRONTEND_DIR))
            print("  Build frontend achevé avec succès.")
        except Exception as e:
            print(f"  Avertissement lors du build frontend : {e}")
            print("  FastAPI fonctionnera en mode API uniquement.")
    else:
        print("  Bundle frontend prêt dans frontend/dist.")


def run_production(port: int = 8000, host: str = "0.0.0.0", open_browser: bool = True):
    """Lance le serveur FastAPI qui distribue l'API et l'application Web sur le même port."""
    if is_port_in_use(port):
        print(f"⚠️  Attention : Le port {port} est déjà utilisé !")
        sys.exit(1)

    print("🚀 [3/3] Démarrage du serveur X-Finder...")
    print("=" * 65)
    print(f"  Interface Web disponible sur : http://localhost:{port}")
    print(f"  Documentation API Swagger    : http://localhost:{port}/docs")
    print("  Appuyez sur Ctrl+C pour arrêter le serveur.")
    print("=" * 65)

    if open_browser:
        def _open():
            time.sleep(1.5)
            try:
                webbrowser.open(f"http://localhost:{port}")
            except Exception:
                pass
        import threading
        threading.Thread(target=_open, daemon=True).start()

    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND_DIR)

    # Exécution de uvicorn via l'interpréteur du venv
    cmd = [
        str(VENV_PYTHON),
        "-m", "uvicorn",
        "app.main:app",
        "--host", host,
        "--port", str(port),
        "--app-dir", str(BACKEND_DIR)
    ]
    try:
        subprocess.run(cmd, env=env)
    except KeyboardInterrupt:
        print("\n🛑 Arrêt du serveur X-Finder. À bientôt !")


def main():
    parser = argparse.ArgumentParser(description="Lanceur officiel X-Finder AI Agent")
    parser.add_argument("--port", type=int, default=8000, help="Port d'écoute du serveur (défaut : 8000)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Hôte d'écoute (défaut : 0.0.0.0)")
    parser.add_argument("--no-browser", action="store_true", help="Ne pas ouvrir automatiquement le navigateur")
    args = parser.parse_args()

    ensure_backend_env()
    ensure_frontend_built()
    run_production(port=args.port, host=args.host, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
