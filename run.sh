#!/usr/bin/env bash
# ==============================================================================
# X-Finder AI Agent - Script de lancement Linux / macOS
# Commande : ./run.sh
# ==============================================================================

set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║          🛡️  X-FINDER AI AGENT - DÉMARRAGE RAPIDE            ║"
echo "╚═══════════════════════════════════════════════════════════════╝"

python3 run.py "$@"
