# Telegram Intelligence Scraper

Modular Python application for authorized OSINT workflows over Telegram data you can already access (public channels, groups, and your own chats). Only messages matching configured keyword categories are stored locally in **MongoDB**.

## Features

- Telethon authentication with persistent session
- Chat discovery and selection
- Keyword-filtered message collection (narcotics, human trafficking, firearms)
- Entity extraction (URLs, domains, emails, phones, mentions, hashtags)
- Analytics with Plotly charts
- CSV/JSON export
- Next.js dashboard (local live MongoDB via FastAPI, or static export on Vercel)
- Data cleanup tool (private chats, runtime files, credentials)

## Requirements

- Python 3.11+
- Node.js 20+ (for the Next.js dashboard)
- Docker Desktop (recommended) **or** a local MongoDB on `127.0.0.1:27017`
- Telegram API credentials from [my.telegram.org/apps](https://my.telegram.org/apps)
- Windows batch launchers included (PowerShell venv activation not required)

## Quick start

```powershell
cd C:\Users\mahdi\Projects\telegram_scraper

# 1. Install dependencies
.\setup.bat

# 2. Start MongoDB (Docker Desktop must be running)
.\mongo.bat

# 3. Add credentials to .env (copy from .env.example)
#    TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE
#    MONGODB_URI=mongodb://127.0.0.1:27017/telegram_scraper

# 4. Log in to Telegram (interactive — enter SMS code)
.\auth.bat

# 5. Scrape a channel or group (pick by index, not private chat)
.\scrape.bat

# 6. Analytics, export, dashboard
.\analytics.bat
.\export.bat
.\dashboard.bat
```

## Workflow

```
auth.bat → discover.bat → scrape.bat → extract.bat → analytics.bat → export.bat → dashboard.bat
```

| Script | Purpose |
|---|---|
| `setup.bat` | Create `.venv` and install dependencies |
| `mongo.bat` | Start MongoDB via Docker Compose |
| `auth.bat` | Telegram login (saves session under `data/`) |
| `discover.bat` | List accessible chats |
| `scrape.bat` | Collect keyword-flagged messages into MongoDB |
| `extract.bat` | Re-run content entity extraction on stored messages |
| `analytics.bat` | Print stats and save Plotly HTML charts to `exports/` |
| `export.bat` | Export CSV + JSON to `exports/` |
| `dashboard.bat` | Launch FastAPI API + Next.js UI (http://localhost:3000) |
| `clear.bat` | Remove private chats and/or reset runtime data |

### Non-interactive scrape (for testing)

After `auth.bat`, pass chat index and message limit:

```powershell
.\.venv\Scripts\python.exe message_scraper.py 1 1000
```

Use a **channel or group index**, not a private chat. Allowed limits: `100`, `500`, `1000`.

### Full local test pipeline

```powershell
.\run_test.bat 1 1000
```

Runs scrape → extract → analytics → export for chat index `1` with limit `1000`.

## Project structure

```
telegram_scraper/
├── server.py              # FastAPI live /api/data (MongoDB)
├── web/                   # Next.js dashboard (local + Vercel)
├── config.py              # Settings from .env
├── telegram_client.py     # Telethon auth and session
├── chat_discovery.py      # List and select chats
├── keyword_filter.py      # Keyword categories
├── message_scraper.py     # Message collection
├── database.py            # MongoDB sessions
├── models.py              # MongoDB document models
├── entity_extractor.py    # Regex entity extraction
├── analytics.py           # Stats and charts
├── exporter.py            # CSV/JSON export
├── clear_data.py          # Cleanup utilities
├── utils.py               # Logging
├── tests/                 # pytest suite
├── data/                  # Telegram session (gitignored)
├── docker-compose.yml     # MongoDB container
├── mongo.bat              # Start MongoDB
├── exports/               # Charts and exports (gitignored)
└── logs/                  # Application logs (gitignored)
```

## Keyword categories

Defined in `keyword_filter.py`:

- **narcotics** — e.g. cocaine, fentanyl, drug trafficking
- **human_trafficking** — e.g. sex trafficking, forced labor
- **firearms** — e.g. ghost gun, weapons trafficking

Only messages matching at least one keyword are stored.

## Configuration

Copy `.env.example` to `.env`:

```env
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE=+1234567890
TELEGRAM_SESSION_NAME=telegram_scraper
DATABASE_URL=mongodb://127.0.0.1:27017/telegram_scraper
MONGODB_URI=mongodb://127.0.0.1:27017/telegram_scraper
LOG_LEVEL=INFO
```

Never commit `.env`, session files, or the database.

## Testing

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

## Data cleanup

```powershell
# Remove private chats only
.\clear.bat --private-chats --yes

# Full reset (session, DB, logs, exports, .env credentials)
.\clear.bat --all --yes
```

After a full reset, re-fill `.env`, run `auth.bat`, then scrape again.

## Dashboard pages

- Overview
- Chats
- Messages
- Keywords
- Analytics
- Entities
- Search
- Export

Launch with `dashboard.bat` → http://localhost:3000

Local stack:
- **Next.js** (`web/`) on port **3000** — UI
- **FastAPI** (`server.py`) on port **8501** — live `/api/data` from MongoDB

`web/.env.local` should contain `DASHBOARD_API_URL=http://127.0.0.1:8501` so the Next route proxies live data. Without the API, Next falls back to `web/public/data/export.json` or the bundled sample.

## Deploy dashboard on Vercel (cloud)

Vercel hosts the same Next.js app under `web/` from `export.json` (read-only). It cannot run Telethon or MongoDB.

```
Local PC: auth → scrape → export.bat → vercel_export.bat
GitHub:   web/ + web/public/data/export.json
Vercel:   Next.js dashboard
```

```powershell
.\export.bat
.\vercel_export.bat
git add -f web/public/data/export.json
git commit -m "Refresh Vercel dashboard export"
git push
```

Set Vercel **Root Directory** to `web`.

### What to tell your boss

| Runs on Vercel | Runs locally only |
|---|---|
| Read-only dashboard | Telegram authentication |
| Shared team URL | Scraping & keyword filtering |
| Auto-refresh from export.json | Live MongoDB custom UI via dashboard.bat |
| Overview / chats / messages / search | Message scraping |
| Public demo URL | MongoDB database |
| | API credentials (`.env`) |

### Vercel setup details

Architecture:

```
Local PC: auth → scrape → export.json
GitHub:   code + optional sanitized export.json
Vercel:   Next.js dashboard (reads export.json)
```

### 1. Export data locally

```powershell
.\export.bat
.\vercel_export.bat
```

This copies `exports/export.json` → `web/public/data/export.json`.

Review the JSON and remove anything sensitive before committing.

### 2. Push to GitHub

```powershell
git add web vercel_export.bat
git commit -m "Add Vercel dashboard"
git push
```

### 3. Create Vercel project

1. Go to [vercel.com/new](https://vercel.com/new)
2. Import your GitHub repo
3. Set **Root Directory** to `web`
4. Framework: **Next.js** (auto-detected)
5. Deploy

Your live URL will look like `https://your-project.vercel.app`.

### 4. Update data later

After new scrapes:

```powershell
.\export.bat
.\vercel_export.bat
git add web/public/data/export.json
git commit -m "Update dashboard data"
git push
```

Vercel redeploys automatically.

### Optional: remote JSON URL

In Vercel → Project → Settings → Environment Variables:

```
EXPORT_JSON_URL = https://your-host/export.json
```

Then you do not need to commit export files to git.

### What to tell your boss

| Runs on Vercel | Runs locally only |
|---|---|
| Read-only dashboard | Telegram authentication |
| Search / chat stats | Message scraping |
| Public demo URL | MongoDB database |
| | API credentials (`.env`) |

## Security notes

- Use only on data you are authorized to access
- Prefer channels/groups over private chats for OSINT collection
- `.gitignore` excludes secrets, sessions, databases, logs, and exports

## License

Educational / authorized OSINT use only. Operate within Telegram's Terms of Service and applicable law.
