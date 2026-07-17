# Telegram Intelligence Scraper

Modular Python application for authorized OSINT workflows over Telegram data you can already access (public channels, groups, and your own chats). Only messages matching configured keyword categories are stored locally in SQLite.

## Features

- Telethon authentication with persistent session
- Chat discovery and selection
- Keyword-filtered message collection (narcotics, human trafficking, firearms)
- Entity extraction (URLs, domains, emails, phones, mentions, hashtags)
- Analytics with Plotly charts
- CSV/JSON export
- Streamlit dashboard
- Data cleanup tool (private chats, runtime files, credentials)

## Requirements

- Python 3.11+
- Telegram API credentials from [my.telegram.org/apps](https://my.telegram.org/apps)
- Windows batch launchers included (PowerShell venv activation not required)

## Quick start

```powershell
cd C:\Users\mahdi\Projects\telegram_scraper

# 1. Install dependencies
.\setup.bat

# 2. Add credentials to .env (copy from .env.example)
#    TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE

# 3. Log in to Telegram (interactive — enter SMS code)
.\auth.bat

# 4. Scrape a channel or group (pick by index, not private chat)
.\scrape.bat

# 5. Analytics, export, dashboard
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
| `auth.bat` | Telegram login (saves session under `data/`) |
| `discover.bat` | List accessible chats |
| `scrape.bat` | Collect keyword-flagged messages into SQLite |
| `extract.bat` | Re-run content entity extraction on stored messages |
| `analytics.bat` | Print stats and save Plotly HTML charts to `exports/` |
| `export.bat` | Export CSV + JSON to `exports/` |
| `dashboard.bat` | Launch Streamlit UI |
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
├── app.py                 # Streamlit entry point
├── dashboard.py           # Dashboard pages and helpers
├── config.py              # Settings from .env
├── telegram_client.py     # Telethon auth and session
├── chat_discovery.py      # List and select chats
├── keyword_filter.py      # Keyword categories
├── message_scraper.py     # Message collection
├── database.py            # SQLAlchemy engine/sessions
├── models.py              # ORM models
├── entity_extractor.py    # Regex entity extraction
├── analytics.py           # Stats and charts
├── exporter.py            # CSV/JSON export
├── clear_data.py          # Cleanup utilities
├── utils.py               # Logging
├── tests/                 # pytest suite
├── data/                  # Session + SQLite (gitignored)
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
DATABASE_URL=sqlite:///data/telegram_scraper.db
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
- Chat Explorer (private chats hidden by default)
- Analytics
- Entity Explorer
- Search
- Export

Launch with `dashboard.bat` → http://localhost:8501

## Deploy dashboard on Streamlit Cloud (recommended)

Streamlit Cloud cannot run the Telethon scraper, SQLite, or Telegram login. It **can** host the **read-only dashboard** from `app.py` using exported JSON.

Architecture:

```
Local PC: auth → scrape → export.json → streamlit_export.bat
GitHub:   code + demo/export.sample.json (or your real demo/export.json)
Streamlit Cloud: app.py reads export.json
```

### 1. Export data locally

```powershell
.\export.bat
.\streamlit_export.bat
```

This copies `exports/export.json` → `demo/export.json`.

Review the JSON and remove anything sensitive before committing.

### 2. Push to GitHub

Commit the app and sample data (minimum for a working demo):

```powershell
git add app.py dashboard.py export_dashboard.py demo/export.sample.json .streamlit requirements.txt
git commit -m "Prepare Streamlit Cloud deployment"
git push
```

To publish **your real scraped data** (gitignored by default):

```powershell
git add -f demo/export.json
git commit -m "Update Streamlit dashboard data"
git push
```

### 3. Create Streamlit Cloud app

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. **New app** → select your GitHub repo
3. **Main file path:** `app.py`
4. Deploy

The app starts in **export-only mode** using `demo/export.sample.json` until you push `demo/export.json`.

### 4. Optional secrets

You only need secrets if you plan to run the full SQLite dashboard on Streamlit (not typical). For export-only viewing, skip secrets.

If needed, in Streamlit → App settings → Secrets:

```toml
TELEGRAM_API_ID = "your_api_id"
TELEGRAM_API_HASH = "your_api_hash"
TELEGRAM_PHONE = "+1234567890"
```

See `.streamlit/secrets.toml.example`.

### 5. Update data later

```powershell
.\export.bat
.\streamlit_export.bat
git add -f demo/export.json
git commit -m "Refresh dashboard export"
git push
```

Streamlit Cloud redeploys on push (or use **Reboot app** in the dashboard).

### What to tell your boss

| Runs on Streamlit Cloud | Runs locally only |
|---|---|
| Read-only dashboard | Telegram authentication |
| Overview / chats / messages / search | Message scraping |
| Public demo URL | SQLite database |
| | API credentials (`.env`) |

## Deploy dashboard on Vercel (alternative)

Vercel cannot run the Telethon scraper, SQLite, or Telegram login. It **can** host the **read-only web dashboard** in `web/`.

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
| Public demo URL | SQLite database |
| | API credentials (`.env`) |

## Security notes

- Use only on data you are authorized to access
- Prefer channels/groups over private chats for OSINT collection
- `.gitignore` excludes secrets, sessions, databases, logs, and exports

## License

Educational / authorized OSINT use only. Operate within Telegram's Terms of Service and applicable law.
