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

## Security notes

- Use only on data you are authorized to access
- Prefer channels/groups over private chats for OSINT collection
- `.gitignore` excludes secrets, sessions, databases, logs, and exports

## License

Educational / authorized OSINT use only. Operate within Telegram's Terms of Service and applicable law.
