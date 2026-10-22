# 🛡️ X-Finder : Agent IA Personnel Autonome avec Tool Calling

> **Assignment de cours** : Développer un agent IA personnel capable d'utiliser des outils externes pour effectuer des tâches concrètes à la demande de l'utilisateur.  
> **Spécialité X-Finder** : OSINT (Open Source Intelligence), Cyber Threat Intelligence (CTI), Détection d'Opportunités (Stages, Emplois, Hackathons, CTF) & Recherche Multimodale (Texte + Image).  
> **Auteur** : Kokou Olivier FIABI (`lynxxoven`)  
> **Plateformes supportées** : Linux, Windows, macOS  
> **Fournisseur LLM** : RodiumAI (`https://api.rodiumai.io/v1`) — Modèles : Gemini 2.5 Flash Lite, Gemini 3.8 Flash, Claude 3.5 Sonnet  

---

## 📑 Table des Matières
1. [Vue d'ensemble et Spécialisation](#-vue-densemble-et-spécialisation)
2. [Matrice d'Évaluation (Conformité 100 % du Barème)](#-matrice-dévaluation-du-projet)
3. [Architecture Technique](#-architecture-technique)
4. [Inventaire des Outils Connectés](#-inventaire-des-outils-connectés)
5. [Installation et Lancement Rapide](#-installation-et-lancement-rapide)
   - [Lancement sous Linux / macOS](#lancement-sous-linux--macos)
   - [Lancement sous Windows](#lancement-sous-windows)
   - [Lancement Manuel / Développeur](#lancement-manuel)
6. [Guide de Test et Évaluation pour l'Enseignant](#-guide-de-test-pour-lenseignant)
7. [Sécurité et Gestion des Données Sensibles](#-sécurité-et-gestion-des-données-sensibles)
8. [Déploiement en Ligne (Lien Public)](#-modalités-de-soumission-et-déploiement-en-ligne)

---

## 🎯 Vue d'ensemble et Spécialisation

Contrairement aux chatbots conversationnels traditionnels qui se limitent à générer du texte, **X-Finder** est un **agent autonome d'action**. Il implémente le patron architectural de **Tool Calling dynamique** :

1. **Compréhension & Planification** : L'agent analyse l'intention utilisateur en langage naturel.
2. **Sélection dynamique des outils** : Il choisit en temps réel le ou les outils pertinents dans son registre (OpenAI function calling standard).
3. **Exécution & Traçabilité** : Les outils sont exécutés de manière sécurisée et chaque appel est journalisé (arguments, durée en millisecondes, statut, résultat).
4. **Enchaînement Multi-Outils (Multi-tool Chaining)** : L'agent peut combiner 3, 4 voire 5 outils séquentiellement pour résoudre un défi complexe (ex: calendrier ➔ Notion ➔ recherche Web ➔ préparation d'email).
5. **Human-in-the-Loop (Sécurité)** : Les actions à fort impact (envoi réel d'email, suppression d'événement) requièrent obligatoirement une confirmation explicite via une carte interactive dans l'interface.
6. **Reconnaissance Multimodale** : Capacité de téléverser une image pour extraction OCR, analyse de métadonnées EXIF et renseignement visuel.
7. **RAG Local Intégré** : Indexation et recherche sémantique TF-IDF dans la base de connaissances documentaire locale (`data/knowledge/`).

---

## 📊 Matrice d'Évaluation du Projet

Le projet a été développé en stricte adéquation avec les critères d'évaluation du sujet :

| Critère d'Évaluation | Poids | Implémentation dans X-Finder | Outils & Fichiers Clés |
|---|:---:|---|---|
| **Interface de chat et déploiement** | **10 %** | Interface Web moderne HUD Cyber (React + Vite), responsive, historique de sessions, sélecteur de modèle LLM, et distribution tout-en-un via FastAPI. | `frontend/src/App.tsx`, `run.py` |
| **Sélection dynamique des outils & agent** | **15 %** | Boucle autonome d'agent multi-tours (`MAX_AGENT_LOOPS = 8`), dispatching d'arguments JSON et gestion d'erreurs sans crash. | `backend/app/agent/core.py`, `registry.py` |
| **Recherche Internet et actualités** | **10 %** | API Tavily Search officielle avec extraction d'actualités récentes et citations de liens sources. Repli DuckDuckGo automatique si clé absente. | `backend/app/tools/web_search.py` |
| **Intégration météo** | **5 %** | Météo actuelle, prévisions sur plusieurs jours et comparaison multi-villes (ex: Lomé vs Accra). Repli Open-Meteo gratuit sans clé. | `backend/app/tools/weather.py` |
| **Intégration Google Calendar** | **15 %** | Consultation des événements à venir, recherche par date/mot-clé, création, mise à jour et suppression (avec confirmation). | `backend/app/tools/calendar_tool.py` |
| **Intégration email (SMTP)** | **10 %** | Rédaction en langage naturel, vérification des champs requis, présentation du brouillon et **confirmation utilisateur obligatoire** avant envoi SMTP. | `backend/app/tools/email_tool.py` |
| **Intégration Notion** | **15 %** | Recherche de pages/notes, lecture de blocs, création de page et ajout de contenu (`append`). | `backend/app/tools/notion_tool.py` |
| **Intégration Google Drive** | **10 %** | Recherche de fichiers par titre ou contenu, lecture de Google Docs et fichiers texte, synthèse documentaire. | `backend/app/tools/drive_tool.py` |
| **Sécurité, fiabilité & robustesse** | **10 %** | `.env` strictement protégé et ignoré, variables d'environnement, validation des entrées Pydantic, gestion des exceptions réseau. | `app/config.py`, `.gitignore` |
| **Total** | **100 %** | **Toutes les fonctionnalités obligatoires + super-pouvoirs OSINT / CTI / Hunter + Multimodal + RAG** | |

---

## 🏗️ Architecture Technique

```
x_finder/
├── backend/
│   ├── app/
│   │   ├── agent/
│   │   │   ├── core.py              # Boucle de raisonnement et Tool Calling multi-tours
│   │   │   ├── prompts.py           # Prompt système X-Finder (règles et sécurité)
│   │   │   └── registry.py          # Registre des schémas d'outils et dispatching
│   │   ├── tools/
│   │   │   ├── web_search.py        # Tavily Search API + repli DuckDuckGo
│   │   │   ├── weather.py           # WeatherAPI + repli Open-Meteo multi-villes
│   │   │   ├── calendar_tool.py     # Google Calendar API (view, search, add, del)
│   │   │   ├── email_tool.py        # Envoi SMTP avec confirmation obligatoire
│   │   │   ├── notion_tool.py       # Notion API (search, read, create, append)
│   │   │   ├── drive_tool.py        # Google Drive API (search, read text/docs)
│   │   │   ├── osint_tools.py       # CTI lookup, chasse aux stages/CTF, recon profil
│   │   │   ├── vision_recon.py      # Analyse visuelle multimodale (Gemini Vision)
│   │   │   └── rag_engine.py        # Moteur RAG local (TF-IDF sur playbooks)
│   │   ├── database/
│   │   │   ├── db.py                # Configuration SQLAlchemy SQLite
│   │   │   └── models.py            # Modèles Conversation, Message, ToolExecution, PendingConfirmation
│   │   ├── config.py                # Gestion des variables d'environnement (Pydantic)
│   │   └── main.py                  # API FastAPI et distribution des fichiers statiques
│   ├── tests/
│   │   ├── test_tools.py            # Tests unitaires des 9 outils
│   │   └── test_api.py              # Tests d'intégration des endpoints FastAPI
│   ├── requirements.txt             # Dépendances Python
│   └── .env.example                 # Modèle de configuration des secrets
├── frontend/
│   ├── src/
│   │   ├── components/              # Sidebar, ChatInput, MessageItemView, ConfirmationCard, ToolsModal
│   │   ├── api/client.ts            # Client API REST
│   │   ├── types/index.ts           # Interfaces TypeScript
│   │   ├── App.tsx                  # Composant HUD principal
│   │   ├── App.css                  # Design Cyber / OSINT épuré
│   │   └── main.tsx
│   ├── dist/                        # Bundle React de production pré-compilé
│   ├── package.json
│   └── vite.config.ts
├── data/
│   ├── knowledge/                   # Documents indexés par le RAG (playbooks, cours)
│   └── uploads/                     # Dossier d'upload pour analyse visuelle
├── run.py                           # Lanceur universel multi-plateforme (Windows & Linux)
├── run.sh                           # Lanceur rapide Linux / macOS
├── run.bat                          # Lanceur rapide Windows Batch
├── .gitignore                       # Protection stricte des clés et tokens
└── README.md                        # Documentation officielle
```

---

## 🛠️ Inventaire des Outils Connectés

1. `search_web` : Recherche en direct sur Internet et actualités via Tavily Search API (avec URLs sources).
2. `get_weather` : Météo actuelle, prévisions et comparateur multi-villes.
3. `list_calendar_events` : Affichage des événements à venir dans Google Calendar.
4. `search_calendar_events` : Recherche d'événements par date ou mot-clé.
5. `create_calendar_event` : Création et planification d'un nouvel événement.
6. `delete_calendar_event` : Suppression d'un événement (avec confirmation préalable).
7. `prepare_email_draft` : Rédige et présente un brouillon pour confirmation obligatoire.
8. `send_email_confirmed` : Expédie l'email via SMTP après feu vert de l'utilisateur.
9. `search_notion` : Recherche de pages et notes dans Notion.
10. `read_notion_page` : Lecture intégrale du contenu d'une page Notion.
11. `create_notion_page` : Création d'une nouvelle note dans Notion.
12. `append_to_notion_page` : Ajout de contenu à une page Notion existante.
13. `search_drive_files` : Recherche de fichiers dans Google Drive.
14. `read_drive_file_content` : Extraction textuelle de Google Docs et fichiers texte.
15. `recon_social_profile` : Reconnaissance OSINT sur profils (LinkedIn, YouTube, GitHub).
16. `cti_threat_lookup` : Veille de cybermenaces (CVE, ransomwares, IOCs, exploit intelligence).
17. `hunt_opportunities` : Chasse aux stages, offres d'emploi, hackathons et compétitions CTF.
18. `analyze_image_intel` : Analyse visuelle multimodale par image (OCR, EXIF, architecture).
19. `query_local_knowledge` : RAG local sur les playbooks et guides de sécurité.

---

## 🚀 Installation et Lancement Rapide

### Prérequis
- **Python 3.10+**
- **Node.js v18+** (uniquement si vous souhaitez recompiler le frontend, sinon le bundle compilé `frontend/dist` est déjà inclus !)

### 1. Cloner le projet
```bash
git clone https://github.com/votre-compte/x-finder.git
cd x_finder
```

### 2. Configuration des variables d'environnement
Copiez le modèle `.env.example` en `.env` :
```bash
cp .env.example .env
```
Renseignez votre clé `RODIUMAI_API_KEY` (fournie par RodiumAI ou l'enseignant).  
> **Note pour l'évaluation** : Grâce aux **replis automatiques intelligents (Zero-Key Fallbacks)** intégrés, l'application fonctionne immédiatement pour les tests même si vous n'avez pas encore configuré vos clés Tavily, Google Cloud ou Notion !

---

### Lancement sous Linux / macOS

```bash
chmod +x run.sh
./run.sh
```
*Ou directement via Python :*
```bash
python3 run.py
```

### Lancement sous Windows

Double-cliquez sur `run.bat` ou exécutez dans un terminal PowerShell / CMD :
```cmd
run.bat
```
*Ou directement :*
```cmd
python run.py
```

---

### Accès à l'application

Une fois le serveur lancé :
- 🌐 **Interface Web de Chat** : [http://localhost:8000](http://localhost:8000)
- 📖 **Documentation Swagger API** : [http://localhost:8000/docs](http://localhost:8000/docs)
- 🩺 **Vérification de santé (Health Check)** : [http://localhost:8000/api/health](http://localhost:8000/api/health)

---

## 🧪 Guide de Test pour l'Enseignant

Pour évaluer rapidement le comportement de l'agent et constater la sélection dynamique des outils, vous pouvez saisir les requêtes de test suivantes :

### Test 1 : Recherche Internet & Actualités (Tavily)
> « Quelles sont les dernières actualités concernant l'intelligence artificielle ? »  
> *L'agent invoque `search_web`, synthétise l'information et fournit les liens sources consultés.*

### Test 2 : Météo & Comparaison Multi-Villes
> « Quelle est la météo actuelle à Lomé et comment se compare-t-elle à celle d'Accra ? »  
> *L'agent appelle `get_weather` avec `cities: "Lomé, Accra"` et génère un tableau comparatif de température, humidité et prévisions.*

### Test 3 : Google Calendar & Gestion d'Agenda
> « Quels sont mes événements programmés pour demain ? »  
> *L'agent appelle `list_calendar_events` et liste les réunions.*  
> « Planifie une réunion intitulée 'Point d'avancement IA' vendredi à 14h. »  
> *L'agent appelle `create_calendar_event` et confirme la création.*

### Test 4 : Notion (Recherche et Création)
> « Retrouve mes notes sur le Machine Learning dans Notion et résume-les. »  
> *L'agent appelle `search_notion` puis `read_notion_page` et répond à partir du contenu extrait.*

### Test 5 : Google Drive (Recherche et Lecture documentaire)
> « Retrouve ma proposition de projet dans Google Drive et résume ses points clés. »  
> *L'agent sélectionne `search_drive_files`, extrait le document avec `read_drive_file_content` et synthétise le projet.*

### Test 6 : Sécurité & Confirmation d'Email (Human-in-the-Loop)
> « Rédige un email pour professeur@universite.fr pour lui transmettre le lien de rendu de l'assignment. »  
> *L'agent appelle `prepare_email_draft`, affiche le brouillon et fait apparaître la **carte de confirmation interactive**. Aucun email n'est expédié tant que vous ne cliquez pas sur **'Valider et Expédier'**.*

### Test 7 : 🏆 Défi Final (Enchaînement Multi-Outils dans une même tâche)
> « Consulte mon Google Calendar pour demain, retrouve dans Notion mes notes sur le Machine Learning, recherche les actualités récentes sur les agents IA et prépare un email pour professeur@universite.fr résumant ces éléments. »  
> *L'agent enchaîne méthodiquement les appels à `list_calendar_events`, `search_notion`, `search_web`, puis prépare le brouillon d'email complet.*

### Test 8 : Spécialités X-Finder (OSINT, CTI & Multimodal)
- **CTI** : « Analyse la menace CVE-2024-3094 et ses conséquences pour les serveurs Linux. »
- **Chasseur d'Opportunités** : « Chasse les offres de stages et les compétitions CTF actives en cybersécurité. »
- **Image Multimodale** : Cliquez sur le bouton *Image / Média*, chargez une capture d'écran ou un schéma technique et demandez « Analyse cette image pour en extraire le texte et les alertes de sécurité ».

---

## 🔒 Sécurité et Gestion des Données Sensibles

- **Zéro Clé en Dur** : Aucune clé API, mot de passe ou jeton OAuth n'est inscrit dans le code source.
- **Exclusion Git Stricte** : Le fichier `.gitignore` bloque rigoureusement `.env`, `credentials.json`, `token.json`, `chat.db` et les logs d'expédition.
- **Principe du Moindre Privilège** : Les scopes OAuth sont limités au strict nécessaire (`calendar` et `drive.readonly`).
- **Isolation Sandbox** : Si un service n'est pas relié à un compte de production, un mode Bac à Sable (Sandbox) sécurisé enregistre les actions dans des fichiers locaux de démonstration sans exposer de comptes personnels.

---

## 🌐 Modalités de Soumission et Déploiement en Ligne

Conformément à la consigne :
> *« La soumission attendue est le lien public vers l'interface de chat déployée et fonctionnelle. »*

Comme le backend FastAPI sert directement le bundle React précompilé sur son port racine, l'ensemble de l'application (backend + frontend) peut être déployé en **un seul processus**.

### Déploiement rapide sur le Cloud (ex: Render / Railway / VPS) :
1. Créez un Web Service pointant sur votre repository GitHub.
2. Commande de démarrage (Start Command) :
   ```bash
   uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
   ```
3. Définissez la variable d'environnement `RODIUMAI_API_KEY` dans le tableau de bord.
4. L'URL publique fournie (ex: `https://x-finder-agent.onrender.com`) est immédiatement prête à être remise à l'enseignant pour évaluation en direct.

### Déploiement sur Vercel (GitHub + PostgreSQL) :
1. Créez une base PostgreSQL persistante, par exemple sur Supabase, puis importez le dépôt `LynxxoV9/x-finder` dans Vercel en gardant la racine du dépôt comme répertoire du projet.
2. Dans **Settings → Environment Variables**, ajoutez `DATABASE_URL` (URL PostgreSQL), `RODIUMAI_API_KEY` et les autres clés d'intégration nécessaires. Ne mettez aucun secret dans Git. SQLite reste réservé au développement local.
3. Déployez. Vercel construit le frontend et l'API FastAPI ; avec GitHub connecté, chaque push sur la branche de production déclenche un nouveau déploiement. Les autres branches créent des prévisualisations.

Les images téléversées par l'API sont traitées en mémoire ; aucun stockage de fichiers local n'est requis. Configurez les variables de base de données dans chaque environnement Vercel utilisé (Production, Preview et Development).

### Exposition publique instantanée via ngrok :
Si vous hébergez temporairement depuis votre machine :
```bash
./run.sh
# Dans un second terminal :
ngrok http 8000
```
L'URL générée par ngrok (`https://xxxx.ngrok-free.app`) donne un accès public direct à l'interface de chat complète.

---

## 📝 Résumé des Commandes Utiles

```bash
# 1. Lancer l'application complète
python3 run.py

# 2. Exécuter la suite de tests automatisés (11 tests unitaires et d'intégration)
cd backend && venv/bin/pytest tests/ -v

# 3. Recompiler le frontend si modifications visuelles
cd frontend && npm run build
```

*Développé avec rigueur et passion pour l'intelligence artificielle agentique et la cybersécurité.*
