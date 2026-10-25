#!/usr/bin/env python3
"""
Assistant de configuration Google Workspace (Calendar & Drive) pour X-Finder.
Permet d'authentifier en une seule commande votre vrai compte Google
avec les permissions nécessaires pour Google Calendar et Google Drive (lecture).
"""

import sys
import os
from pathlib import Path

# Résolution des chemins du projet
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive.readonly",
]

def main():
    print("=" * 65)
    print("🛡️  X-Finder : Assistant d'authentification Google Calendar & Drive")
    print("=" * 65)

    # 1. Vérification des bibliothèques
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.oauth2.credentials import Credentials
    except ImportError:
        print("\n❌ Les bibliothèques Google ne sont pas installées dans cet environnement.")
        print("Installez-les avec :")
        print("  pip install google-auth-oauthlib google-api-python-client")
        sys.exit(1)

    # 2. Recherche de credentials.json
    credentials_candidates = [
        PROJECT_ROOT / "credentials.json",
        PROJECT_ROOT / "backend" / "credentials.json",
    ]
    secrets_file = next((p for p in credentials_candidates if p.exists()), None)

    if not secrets_file:
        print("\n⚠️  Fichier 'credentials.json' introuvable !")
        print("\nPour connecter votre VRAI compte Google :")
        print("1. Rendez-vous sur Google Cloud Console : https://console.cloud.google.com/")
        print("2. Créez un projet (ou sélectionnez un projet existant).")
        print("3. Activez les 2 APIs suivantes dans 'APIs et services' > 'Bibliothèque' :")
        print("   - Google Calendar API")
        print("   - Google Drive API")
        print("4. Configurez l'écran de consentement OAuth (Type utilisateur : Externe, ajoutez votre email en utilisateur test).")
        print("5. Créez des identifiants : 'Identifiants' > 'Créer des identifiants' > 'ID client OAuth'")
        print("   - Type d'application : 'Application de bureau' (Desktop App)")
        print("6. Téléchargez le fichier JSON et placez-le sous le nom 'credentials.json' à la racine de x_finder :")
        print(f"   Destination : {PROJECT_ROOT / 'credentials.json'}")
        print("\nUne fois le fichier placé, relancez simplement :")
        print("  python3 scripts/setup_google_auth.py")
        sys.exit(1)

    print(f"\n✅ Fichier d'identifiants détecté : {secrets_file}")
    print("\nLancement du flux d'authentification OAuth2 dans votre navigateur...")
    print("Une page Google va s'ouvrir pour autoriser l'accès à Calendar et Drive.")

    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(secrets_file), SCOPES)
        creds = flow.run_local_server(port=0)

        token_path = PROJECT_ROOT / "token.json"
        with open(token_path, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

        # Copie de sauvegarde dans backend si besoin
        backend_token = PROJECT_ROOT / "backend" / "token.json"
        with open(backend_token, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

        print("\n" + "=" * 65)
        print("🎉 Authentification Google réussie avec succès !")
        print(f"Jeton généré et sauvegardé dans : {token_path}")
        print("X-Finder peut désormais lire vos vrais documents Google Drive")
        print("et consulter/gérer votre vrai agenda Google Calendar.")
        print("=" * 65)

    except Exception as e:
        print(f"\n❌ Erreur lors de l'authentification : {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
