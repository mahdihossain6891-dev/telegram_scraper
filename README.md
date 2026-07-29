# Threat Console — Telegram OSINT Intelligence Platform

Modular Python + Next.js application for **authorized OSINT** over Telegram data you already can access (public channels, groups, and your own chats). Keyword-flagged messages land in **MongoDB**, then surface in a SOC-style Threat Console with risk scoring, behavioral analytics, AI investigation (**Sébastien**), and an isolated simulation lab.

<!-- Add docs/assets/threat-console.png after a local screenshot — see docs/assets/README.md -->
<!-- ![Threat Console](docs/assets/threat-console.png) -->

<p align="center">
  <em>Dashboard · Threat Monitoring · Alerts · Channels · Users · Analytics · Behavioral Analytics · Threat Intelligence · Simulator · Sébastien AI</em>
</p>

---

## 📚 Table of Contents

- [📥 Threat Console Slide Deck (Gamma)](docs/presentations/THREAT_CONSOLE_GAMMA.md)
- [📊 Recruiter Slide Deck (Project Flow Walkthrough)](docs/presentations/RECRUITER_ONEPAGER.md)
- [🛰️ Threat Intelligence Engine (TIE) Integration](docs/TIE_INTEGRATION.md)
- [📈 Behavioral Analytics Module](docs/BEHAVIORAL_ANALYTICS.md)
- [⚡ Quick Run Instructions (Run in 30 Seconds)](#-quick-run-instructions-run-in-30-seconds)
- [🌟 Key Application Features](#-key-application-features)
- [📄 Telegram Export JSON File Format Guide](docs/EXPORT_JSON.md)
- [📥 How to Scrape Telegram with Telethon](#-how-to-scrape-telegram-with-telethon)
- [🧠 How Sébastien AI & Vector Search Work](#-how-sébastien-ai--vector-search-work)
- [📖 Architecture & Tech Stack](#-architecture--tech-stack)
- [🔗 Project Links](#-project-links)
- [☁️ Deploy Dashboard on Vercel](#️-deploy-dashboard-on-vercel)
- [⚙️ Configuration](#️-configuration)
- [🧪 Testing](#-testing)
- [🔒 Security](#-security)

---

## ⚡ Quick Run Instructions (Run in 30 Seconds)

### Prerequisites

- **Python 3.11+**
- **Node.js 20+** (Threat Console UI)
- **Docker Desktop** (recommended for MongoDB) **or** local MongoDB on `127.0.0.1:27017`
- Telegram API credentials from [my.telegram.org/apps](https://my.telegram.org/apps)

### Clone & start (Windows)

```powershell
git clone https://github.com/mahdihossain6891-dev/telegram_scraper.git
cd telegram_scraper

# 1. Create venv + install Python/Node deps
.\setup.bat

# 2. Start MongoDB (Docker Desktop must be running)
.\mongo.bat
# equivalent: docker compose up -d

# 3. Add credentials to .env (copied from .env.example by setup.bat)
#    TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE
#    MONGODB_URI=mongodb://127.0.0.1:27017/telegram_scraper

# 4. Log in to Telegram (interactive — SMS / app code)
.\auth.bat

# 5. Optional: scrape a channel/group (pick by index, not private chat)
.\scrape.bat

# 6. Launch FastAPI + Next.js Threat Console
.\dashboard.bat
```

After the services are up:

| Service | URL |
|---------|-----|
| **Threat Console UI** | http://localhost:3000 |
| **FastAPI + Swagger** | http://127.0.0.1:8510/docs |
| **Health** | http://127.0.0.1:8510/api/health |

### Full CLI pipeline (optional)

```
auth.bat → discover.bat → scrape.bat → extract.bat → analytics.bat → export.bat → dashboard.bat
```

| Script | Purpose |
|--------|---------|
| `setup.bat` | Create `.venv` and install dependencies |
| `mongo.bat` | Start MongoDB via Docker Compose |
| `auth.bat` | Telegram login (session under `data/`) |
| `discover.bat` | List accessible chats |
| `scrape.bat` | Collect keyword-flagged messages into MongoDB |
| `extract.bat` | Re-run entity extraction on stored messages |
| `analytics.bat` | Stats + Plotly HTML charts → `exports/` |
| `export.bat` | CSV + JSON → `exports/` |
| `dashboard.bat` | FastAPI + Next.js UI |
| `clear.bat` | Remove private chats and/or reset runtime data |

Non-interactive scrape (after auth):

```powershell
.\.venv\Scripts\python.exe message_scraper.py 1 1000
```

Use a **channel or group index**, not a private chat. Allowed limits: `100`, `500`, `1000`.

---

## 🌟 Key Application Features

### Collect
- Telethon authentication with persistent session
- Chat discovery and selection
- Keyword-filtered collection (**narcotics**, **human trafficking**, **firearms**)
- Auto-update loop and dashboard-triggered scrapes

### Enrich
- Entity extraction (URLs, domains, emails, phones, mentions, hashtags)
- Deterministic risk scoring (message / person / channel)
- Personnel activity rollups
- Behavioral analytics profiles

### Monitor (Threat Console)

The Next.js UI at `http://localhost:3000` is the full SOC console. Toggle **Live** vs **Simulation** in the sidebar to switch between production MongoDB and the isolated simulation database.

| Page | Route | Purpose |
|------|-------|---------|
| **Dashboard** | `/` | Command overview, scrape controls, risk posture |
| **Threat Monitoring** | `/?page=Intel` | Flagged message and entity intel feed |
| **Alerts** | `/?page=Ops` | Telegram bot / channel alert delivery |
| **Channels** | `/?page=Sources` | Source chat summaries and activity |
| **Users** | `/?page=Cases` | Personnel / case rollups with risk scores |
| **Analytics** | `/?page=Analytics` | Charts, trends, collection breakdown |
| **Threat Intelligence** | `/?page=ThreatIntelligence` | TIE ingest, engine mode, intelligence reports |
| **Simulator** | `/?page=ThreatSimulation` | Scenario lab, synthetic traffic, evaluation demos |
| **Behavioral Analytics** | `/behavioral-analytics` | UEBA-style behavior profiles and scoring |
| **Sébastien AI** | `/ai` | Evidence-grounded investigation copilot (RAG) |
| **Settings** | `/settings` | Environment and console configuration |

Data source: live MongoDB via FastAPI (`server.py`), simulation DB when simulation mode is active, or static `export.json` on Vercel (read-only).

### Investigate & train
- **Sébastien** — evidence-grounded AI (RAG, investigate, reports) at `/ai`
- **Simulator** — isolated simulation DB for safe demos and AI training data
- Evaluation / benchmark toolkit under `evaluation/`

### Export
- CSV / JSON export
- Vercel-ready snapshot via `vercel_export.bat`

---

## 🧠 How Sébastien AI & Vector Search Work

Sébastien is an **opt-in, isolated** AI layer. Scraping, keyword gates, risk scores, and alerts stay deterministic and non-AI.

```
Flagged messages (MongoDB)
        │
        ▼
  Embedding / indexer  →  ai_embeddings (or Qdrant / memory)
        │
        ▼
  RAG retrieve → hydrate evidence → LLM answer / investigate / report
        │
        ▼
  /api/ai/*  →  Threat Console /ai (Sébastien UI)
```

| Piece | Role |
|-------|------|
| `ai/rag/` | Retrieve → prompt → generate |
| `ai/vectorstore/` | MongoDB / Qdrant / in-memory backends |
| `ai/investigation/` | Multi-turn investigation assistant |
| `ai/api/` | FastAPI router mounted at `/api/ai` |

Enable with `AI_*` settings in `.env` (Ollama, OpenRouter, LM Studio, etc.). Details: [`ai/README.md`](ai/README.md) · architecture ADR: [`docs/adr/001-ai-architecture.md`](docs/adr/001-ai-architecture.md).

---

## 📖 Architecture & Tech Stack

```
Telegram (Telethon)
  → keyword-gated scrape
  → MongoDB (messages, users, chats, entities, risk, AI collections…)
  → FastAPI (server.py :8510)
  → Next.js Threat Console (web/ :3000)
  → optional export.json → Vercel (read-only)
```

| Layer | Tech |
|-------|------|
| Collection | Python 3.11+, Telethon |
| Storage | MongoDB 7 (Docker Compose) |
| API | FastAPI + Uvicorn |
| UI | Next.js (App Router), ECharts |
| AI | Isolated `ai/` package (RAG / Sébastien) |
| Simulation | Isolated `simulator/` + sim database |
| Evaluation | `evaluation/` metrics & validators |

### Project layout (high level)

```
telegram_scraper/
├── server.py                 # FastAPI live API
├── web/                      # Next.js Threat Console
├── ai/                       # Sébastien / RAG / vectorstore
├── simulator/                # Threat simulation lab
├── evaluation/               # Benchmarks & validators
├── scrape_jobs/              # Background scrape jobs
├── database.py / models.py   # MongoDB access & documents
├── message_scraper.py        # Keyword-gated collection
├── keyword_filter.py         # Category keywords
├── entity_extractor.py       # Regex entities
├── risk_scoring.py           # Deterministic risk
├── behavioral_analytics.py   # Behavior profiles
├── tie_ingest.py             # TIE → Console report ingest
├── tie_engine_mode.py        # TIE engine on/off
├── docker-compose.yml        # MongoDB container
├── docs/                     # TIE, export, behavioral, presentations, assets
└── tests/                    # pytest suite
```

---

## 📥 How to Scrape Telegram with Telethon

1. Create an app at [my.telegram.org/apps](https://my.telegram.org/apps) → put `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` in `.env`
2. `.\auth.bat` — saves session under `data/` (gitignored)
3. `.\discover.bat` — list chats you can access
4. `.\scrape.bat` — only messages matching at least one keyword category are stored

**Keyword categories** (`keyword_filter.py`):

- **narcotics** — e.g. cocaine, fentanyl, drug trafficking
- **human_trafficking** — e.g. sex trafficking, forced labor
- **firearms** — e.g. ghost gun, weapons trafficking

Prefer **channels/groups** over private chats for OSINT collection. Operate only on data you are authorized to access.

**Export packs after scrape:**

```powershell
.\export.bat
```

See also: [Export JSON format](docs/EXPORT_JSON.md) · [TIE integration](docs/TIE_INTEGRATION.md)

---

## 🔗 Project Links

| | URL |
|--|-----|
| **GitHub Repository** | https://github.com/mahdihossain6891-dev/telegram_scraper |
| **Live Frontend (Vercel)** | _Deploy `web/` → set Root Directory to `web` — then replace this line with your `*.vercel.app` URL_ |
| **API Swagger (local)** | http://127.0.0.1:8510/docs _(after `dashboard.bat`)_ |
| **Threat Console deck** | [`docs/presentations/THREAT_CONSOLE_GAMMA.md`](docs/presentations/THREAT_CONSOLE_GAMMA.md) |
| **TIE integration** | [`docs/TIE_INTEGRATION.md`](docs/TIE_INTEGRATION.md) |

Paste Gamma markdown into [gamma.app](https://gamma.app) (**Create with AI**) to generate a PPT/slide walkthrough.

**Copy-paste blurb for mentors / submissions:**

> I have completed the Threat Console (Telegram OSINT Intelligence Platform) project. Please find the details below:
>
> **Project Links**
> - **GitHub Repository:** https://github.com/mahdihossain6891-dev/telegram_scraper
> - **Live Frontend:** _(your Vercel URL)_
> - **API Swagger Documentation:** http://127.0.0.1:8510/docs (local) — or your hosted API `/docs`
>
> **Quick Setup (local)**
> ```bash
> git clone https://github.com/mahdihossain6891-dev/telegram_scraper.git
> cd telegram_scraper
> # Windows: .\setup.bat && .\mongo.bat && fill .env && .\auth.bat && .\dashboard.bat
> ```

---

## ☁️ Deploy Dashboard on Vercel

Vercel hosts the **read-only** Next.js app under `web/` from `export.json`. It cannot run Telethon or MongoDB.

```
Local PC:  auth → scrape → export.bat → vercel_export.bat
GitHub:    web/ + web/public/data/export.json
Vercel:    Next.js dashboard (Root Directory = web)
```

```powershell
.\export.bat
.\vercel_export.bat
git add -f web/public/data/export.json
git commit -m "Refresh Vercel dashboard export"
git push
```

1. [vercel.com/new](https://vercel.com/new) → import this repo  
2. Set **Root Directory** to `web`  
3. Deploy → update the **Live Frontend** link in [Project Links](#-project-links)

| Runs on Vercel | Runs locally only |
|----------------|-------------------|
| Read-only dashboard | Telegram auth & scraping |
| Shared demo URL | Live MongoDB + FastAPI |
| Search / overview from export | Alerts, Sébastien (live DB), Simulator |

Optional: set Vercel env `EXPORT_JSON_URL` to a hosted JSON URL so you do not commit export files.

---

## ⚙️ Configuration

Copy `.env.example` → `.env` (done automatically by `setup.bat`):

```env
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE=+1234567890
TELEGRAM_SESSION_NAME=telegram_scraper
DATABASE_URL=mongodb://127.0.0.1:27017/telegram_scraper
MONGODB_URI=mongodb://127.0.0.1:27017/telegram_scraper
LOG_LEVEL=INFO
```

Dashboard proxy (`web/.env.local`):

```env
DASHBOARD_API_URL=http://127.0.0.1:8510
```

Never commit `.env`, session files, or the database. See `.env.example` for AI, alerts, and simulation options.

### Data cleanup

```powershell
# Remove private chats only
.\clear.bat --private-chats --yes

# Full reset (session, DB, logs, exports, .env credentials)
.\clear.bat --all --yes
```

After a full reset, re-fill `.env`, run `auth.bat`, then scrape again.

---

## 🧪 Testing

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

AI / simulator packages also ship tests under `ai/` and `simulator/tests/`.

---

## 🔒 Security

- Use only on data you are **authorized** to access
- Prefer channels/groups over private chats for collection
- `.gitignore` excludes secrets, sessions, databases, logs, and exports
- Simulation mode uses an **isolated** Mongo database so demos never write production intel

## License

Educational / authorized OSINT use only. Operate within Telegram's Terms of Service and applicable law.
