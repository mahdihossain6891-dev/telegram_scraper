# Threat Intelligence Engine (TIE) ↔ Threat Console

How Threat Console connects to the external **Threat Intelligence Engine**.

## What TIE does

TIE is a separate service that can:

1. Receive scraped / flagged traffic from Threat Console (when TIE mode is on)
2. Enrich, classify, and score intelligence
3. Push processed reports back into Threat Console for the **Threat Intelligence** page

Threat Console stays usable **without** TIE — keyword filter, risk scoring, behavioral analytics, and Sébastien work standalone.

## Architecture

```
Telegram scrape (keyword-gated)
        │
        ▼
 Threat Console (FastAPI + MongoDB)
        │  optional (TIE engine ON)
        ▼
 Threat Intelligence Engine  (:8000 by default)
        │  POST processed reports
        ▼
 Threat Console  /api/intelligence/reports
        │
        ▼
 Mongo: tie_intelligence_reports
        │
        ▼
 UI: Threat Intelligence page (/)
```

## Key files

| Path | Role |
|------|------|
| `tie_ingest.py` | Ingest API — `POST /api/intelligence/reports` |
| `tie_engine_mode.py` | Persist TIE on/off mode |
| `tie_process.py` | Start / stop external TIE uvicorn process |
| `web/app/api/tie/[...path]/route.ts` | Next.js proxy → TIE `/api/v1/tie/*` |
| `web/app/api/tie-engine/route.ts` | Console toggle for TIE engine mode |
| `web/app/api/tie-engine/process/` | Start / stop / status for TIE process |
| `web/services/tieService.ts` | Frontend TIE client |
| `web/components/ThreatIntelligencePage.tsx` | Ops UI |
| `web/components/mode/TieEngineProvider.tsx` | Engine mode context |
| `data/tie_engine_mode.json` | Local mode flag (gitignored / runtime) |

## Configuration

**Threat Console `.env`:**

```env
# Shared key TIE must send when posting reports into Console
TIE_INGEST_API_KEY=dev-tie-console-shared-key

# Where Console proxies TIE ops calls
TIE_API_URL=http://127.0.0.1:8000
TIE_ENGINE_ENABLED=0
# Folder containing app/main.py for Start Engine
# TIE_ENGINE_CWD=C:\Users\mahdi\threat translation engine
```

**Next.js `web/.env.local`:**

```env
DASHBOARD_API_URL=http://127.0.0.1:8510
TIE_API_URL=http://127.0.0.1:8000
# Optional:
# TIE_API_KEY=
# TIE_BEARER_TOKEN=
# NEXT_PUBLIC_TIE_ROLE=administrator
```

## Auth (ingest)

TIE → Console reports require:

```http
Authorization: Bearer <TIE_INGEST_API_KEY>
```

(or `X-API-Key: <TIE_INGEST_API_KEY>`)

## Console UI

1. Start Threat Console: `.\dashboard.bat`
2. Open the **Threat Intelligence** page
3. Click **Start Engine** (or flip the TIE switch On) — Console launches the external TIE process and enables scrape forwarding
4. Click **Stop Engine** (or flip Off) to kill the process
5. View health, pipeline, queue, and recent intelligence from the proxied TIE API

Default TIE project path auto-detected as `~/threat translation engine`. Override with:

```env
TIE_ENGINE_CWD=C:\Users\mahdi\threat translation engine
```

## Without TIE

Leave the engine stopped (or `TIE_ENGINE_ENABLED=0`). Scrapes stay in Console’s keyword + risk pipeline only.
