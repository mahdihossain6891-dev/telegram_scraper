# Threat Console — Gamma Presentation

Paste this file into [Gamma](https://gamma.app) (**Create with AI** → paste the prompt at the bottom),  
or paste each `##` section as one card/slide.

**Tone:** SOC / threat-intel product demo · dark premium · concise bullets · no fluff  
**Audience:** stakeholders, demos, handoff

---

## Slide 1 — Title

# Threat Console
### Telegram OSINT Intelligence Platform

Authorized monitoring · keyword detection · behavioral risk · AI investigation

**Sébastien** · Live + Simulation modes · MongoDB · Next.js + FastAPI

---

## Slide 2 — The problem

# Telegram is where threats coordinate

- Trafficking, narcotics, and firearms chatter moves in public channels and groups
- Analysts drown in noise without keyword filters and entity extraction
- Static exports aren’t enough — teams need **live monitoring**, **alerts**, and **investigation tools**
- Training AI / demos must never touch production intel

---

## Slide 3 — What we built

# One console. Full intel loop.

**Threat Console** is a modular OSINT platform that:

1. Collects keyword-flagged Telegram messages you already have access to  
2. Stores them in MongoDB with risk + entities  
3. Surfaces them in a SOC-style dashboard  
4. Scores behavioral risk and relationships  
5. Investigates with **Sébastien** (evidence-grounded AI)  
6. Trains and demos safely in **Simulation mode**

---

## Slide 4 — Product map

# Feature map

| Pillar | Capabilities |
|--------|----------------|
| **Collect** | Auth, discover chats, keyword scrape, auto-update |
| **Enrich** | Entities, personnel activity, risk factors |
| **Monitor** | Dashboard, threat feed, alerts, channels, users |
| **Analyze** | Analytics charts, behavioral profiles |
| **Investigate** | Sébastien — intent → tools → evidence → report |
| **Simulate** | Isolated sim DB, multi-scenario generate, lab UI |
| **Operate** | Settings, dark/light theme, export, Vercel snapshot |

---

## Slide 5 — Architecture

# Architecture at a glance

```
Telegram (Telethon)
        ↓
Keyword filter + scrape jobs
        ↓
MongoDB (live)  |  MongoDB (simulation)   ← isolated
        ↓
FastAPI :8510   —  /api/data · /api/ai · /api/behavioral · /api/mode · /api/simulator
        ↓
Next.js Threat Console :3000
```

- **Live** and **Simulation** share the same UI shell — only the data source changes  
- AI, behavioral, and simulator modules are **opt-in / additive** routers

---

## Slide 6 — Collection pipeline

# Collect: scrape what matters

- Telethon auth with persistent local session  
- Chat discovery — channels & groups (not private DMs by default)  
- **Keyword-only storage** — narcotics · firearms · human trafficking  
- Limits: 100 / 500 / 1000 messages per scrape  
- Dashboard scrape control + optional auto-update loop  
- Demo bot posting for test channels  

**Outcome:** high-signal corpus, not a full Telegram dump

---

## Slide 7 — Keywords & risk

# Keyword intelligence

Three threat categories (configurable):

- **Narcotics** — trafficking language, product slang  
- **Firearms** — ghost guns, weapons trafficking  
- **Human trafficking** — coercion / exploitation signals  

Each stored message carries:

- Matched categories & keyword hits  
- Risk score / risk level / risk factors  
- Timestamp, chat, sender, media metadata  

---

## Slide 8 — Entity extraction

# Entities pulled from message text

| Content | Identifiers | Crypto / contact |
|---------|-------------|------------------|
| URLs · domains · hashtags · mentions | Emails · phones | Wallets · addresses |

- Regex extraction pipeline (+ optional AI NER job)  
- Powers search, relationship graphs, and Sébastien evidence  
- Re-runnable via extract job without re-scraping  

---

## Slide 9 — Threat Console shell

# SOC UI — same shell everywhere

**Monitor**
- Dashboard · Threat Monitoring · Alerts  

**Entities**
- Channels · Users  

**Analyze**
- Analytics · Simulator  

**Intel+**
- Behavioral Analytics · Sébastien  

Also: Live ⇄ Simulation toggle · Scope filters · Dark / light theme · Settings

---

## Slide 10 — Dashboard

# Dashboard (Command)

- Live KPI strip — messages, threats, sources, risk  
- Severity mix + activity trends (ECharts)  
- Scrape control — start / status / progress  
- Simulation-aware: generate dummy traffic without touching live Mongo  
- Scope: chat type, categories, date range, source picker  

---

## Slide 11 — Threat monitoring & alerts

# Threat Monitoring + Alerts

**Threat Monitoring**
- Flagged message feed with keyword badges  
- Filter by category, chat, risk  

**Alerts (Ops)**
- Telegram bot alerts on scrape (optional)  
- Cooldown, multi-category, min-keyword rules  
- In **simulation**: alerts log locally — never spam Telegram  

---

## Slide 12 — Channels & users

# Channels + Users

**Channels (Sources)**
- Monitored chats, volumes, last activity  
- Jump into scoped analysis  

**Users (Cases / Personnel)**
- Sender dossiers from activity rebuild  
- Message counts, groups, risk overlay  
- Bridge into behavioral profiles and Sébastien targets  

---

## Slide 13 — Analytics

# Analytics

- Volume over time  
- Keyword / category breakdowns  
- Top chats and senders  
- Theme-aware charts (dark / light)  
- CLI analytics + Plotly HTML exports for offline packs  

---

## Slide 14 — Behavioral analytics

# Behavioral Analytics

Isolated module · own Mongo collection · own `/api/behavioral` routes

Profiles include:

- Behavior score & status (normal / anomalous)  
- Timing patterns (night activity, spikes)  
- Forwarding / media / deletion signals  
- Soft scoring for sparse datasets (esp. simulation)  

Rebuild from existing messages — never mutates scrape collections  
UI: `/behavioral-analytics`

---

## Slide 15 — Sébastien

# Sébastien — AI Investigation Copilot

Not a chatbot. An **investigation coordinator**.

```
Question → Intent → Entity resolve → Planner → Tools
      → Evidence validation → Context → LLM explain → Report
```

- Evidence-grounded answers with citations  
- Quick actions: Investigate User · Analyze Behavior · Explain Alert · Related Users · Report  
- Saved cases, workflow panel, evidence drawer  
- Control Center: providers, models, generation, cache, prompt reload  
- Works on **live** and **simulation** data (mode-aware DB + RAG)

---

## Slide 16 — Sébastien tools & providers

# Investigation tools + model providers

**Tools (read-only)**  
Risk · Behavior · Alerts · Personnel · Timeline · Relationships · Search · Dashboard · Report

**Providers**
- OpenRouter · Ollama · LM Studio · OpenAI-compatible  
- Chat and embeddings can be split (e.g. OpenRouter chat + local embeds)  
- Vector backend: MongoDB embeddings (shared with FastAPI process)

**Guardrails**
- Unknown intents never reach the LLM  
- Missing / ambiguous entities fail closed  
- Target required before user-scoped investigations  

---

## Slide 17 — Simulation mode

# Simulation mode

Train, demo, and test without production risk.

| | Live | Simulation |
|---|------|------------|
| Database | `telegram_scraper` | `telegram_scraper_simulation` |
| Scrape | Real Telethon | AI / fallback dummy generate |
| Alerts | Telegram (optional) | Local log only |
| UI | Full console | Same pages — sim banner |

- Multi-select scenarios: narcotics · firearms · human trafficking  
- Message volume presets (e.g. 24 / 48 / 80)  
- Auto index + behavioral rebuild after generate  
- Mode toggle on console **and** Sébastien  

---

## Slide 18 — Simulator lab

# Simulator (Threat Simulation lab)

First-class Operate module for pipeline QA:

- Sessions · scenarios · personas · groups  
- Live activity stream  
- Pipeline inspector per message  
- Benchmarks & simulation reports  
- Configuration panel  

Isolated `/api/simulator/*` — additive mount, production data untouched  

---

## Slide 19 — Settings & ops

# Settings & operations

**Shared settings**
- Dark / light theme  
- Telegram API ID · Hash · phone  
- OpenRouter key (auto-wires AI enablement)

**Ops toolkit**
- `dashboard.bat` — API + Next.js  
- `mongo.bat` — Docker MongoDB  
- `auth` / `scrape` / `extract` / `export` / `clear`  
- Auto-update loop with optional Vercel sync  

**Cloud snapshot**
- Export JSON → Vercel read-only dashboard (no Telethon on Vercel)

---

## Slide 20 — Tech stack

# Stack

| Layer | Tech |
|-------|------|
| Collection | Python · Telethon · keyword filter |
| Store | MongoDB · Docker Compose |
| API | FastAPI · scrape jobs · mode router |
| UI | Next.js 15 · React · ECharts |
| AI | RAG · embeddings · planner · OpenRouter/Ollama |
| Quality | pytest · evaluation module · sim benchmarks |

Design: glassmorphism SOC shell · Plus Jakarta Sans · severity color system  

---

## Slide 21 — Demo path (2 minutes)

# Live demo path

1. **Live mode** → Dashboard KPIs & scrape status  
2. **Threat Monitoring** → open a flagged message  
3. **Behavioral** → open a high-score profile  
4. **Sébastien** → `Investigate @username` → evidence + report  
5. **Switch to Simulation** → Generate (multi-scenario)  
6. **Sébastien again** → investigate a sim persona — same UX, safe data  

---

## Slide 22 — Close

# Threat Console

**Collect → Enrich → Monitor → Analyze → Investigate → Simulate**

Authorized Telegram OSINT for teams that need signal, not noise.

Questions?

---

# Gamma AI prompt (paste into Gamma → Create with AI)

Copy everything inside the fence below into Gamma.

```
ROLE
You are designing a stakeholder product deck for "Threat Console" — an authorized Telegram OSINT / threat-intelligence platform. Write like a SOC product demo: precise, capability-first, no hype, no invented features.

VISUAL SYSTEM
- Dark premium glassmorphism SOC aesthetic
- Background: near-black / deep navy (#0b0b12)
- Accent: violet (#8b5cf6 / #a78bfa)
- Severity palette: Low green · Medium amber · High orange · Critical red
- Typography: clean modern sans; mono for IDs / API paths
- Layout: one idea per slide, short bullets, tables where useful, 1–2 diagrams max
- No stock purple-gradient SaaS clichés beyond the defined violet accent
- Include small UI mock cues only as abstract panels (sidebar + KPI strip), not fake screenshots

SLIDE COUNT & STRUCTURE
Create exactly 24 slides in this order. Every slide needs a clear title. Prefer bullets and compact tables over paragraphs.

════════════════════════════════════
PRODUCT FACTS (USE THESE SPECS)
════════════════════════════════════

PRODUCT NAME
Threat Console — Telegram OSINT Intelligence Platform
AI assistant brand: Sébastien (investigation copilot, NOT a chatbot)

PURPOSE
Authorized monitoring of Telegram channels/groups the operator can already access. Only keyword-flagged messages are stored. Live ops + isolated simulation for demos/training/AI without touching production data.

CORE LOOP
Collect → Enrich → Monitor → Analyze → Investigate → Simulate → Validate

STACK
- Collection: Python 3.11+, Telethon, persistent session under data/
- Storage: MongoDB (Docker Compose via mongo.bat); live DB + isolated simulation DB
- API: FastAPI (~port 8510/8501) — /api/data, /api/mode, /api/scrape, /api/personnel, /api/behavioral, /api/alerts, /api/settings/env, /api/ai, /api/simulator, /api/evaluation
- UI: Next.js 15 + React on :3000; ECharts; dark/light theme
- AI: RAG + embeddings (Mongo vector collection), investigation planner, OpenRouter / Ollama / LM Studio / OpenAI-compatible
- Quality: pytest; evaluation/ benchmarking with Intelligence Quality Score (IQS)

KEYWORD CATEGORIES (only matching messages stored)
1) narcotics  2) firearms  3) human_trafficking
Message enrichment: risk_score, risk_level, risk_factors, keyword hits, chat/sender/timestamp/media metadata

ENTITY EXTRACTION
url, domain, email, phone, mention, hashtag, wallet, address
Powers search, relationships, Sébastien evidence; re-runnable without re-scrape

CONSOLE NAV (SOC labels)
Monitor: Dashboard · Threat Monitoring · Alerts
Entities: Channels · Users
Analyze: Analytics · Simulator
Intel+: Behavioral Analytics (/behavioral-analytics) · Sébastien (/ai)
Global: Live ⇄ Simulation mode toggle · Scope filters · Settings · theme

DASHBOARD FUNCTIONALITY
- KPI strip (messages, threats, sources, risk)
- Severity mix + activity trends
- Scrape control (live Telethon) / Generate control (simulation)
- Scope: include private DMs toggle, chat type, keyword categories, chat multi-select, date range
- Auto-refresh (live) or sim feed indicator

ALERTS FUNCTIONALITY
- Optional Telegram bot alerts on scrape (TELEGRAM_ALERTS_*)
- Rules: cooldown, multi-category-only, min keywords
- Simulation: alerts logged locally — never sent to Telegram

PERSONNEL / USERS
- Rebuild user_activity from messages
- Dossiers: message counts, groups, risk overlay, last seen
- API: GET /api/personnel, GET /api/personnel/{id}, POST rebuild

BEHAVIORAL ANALYTICS (isolated module)
- Own collection behavioral_analytics; own /api/behavioral/* routes
- Profiles: behavior score/status, night activity, spikes, forwarding/media/deletion signals
- Soft scoring for sparse/sim data so scores aren’t all zero
- POST /api/behavioral/rebuild recomputes from messages/users/chats — never mutates scrape source

SÉBASTIEN — FUNCTIONAL PIPELINE
User question
→ Intent classification (investigate_user, analyze_behavior, explain_alert, timeline, relationships, dashboard_summary, report, …; unknown blocks LLM)
→ Entity resolution (@username / Telegram ID / display name; ambiguous → ask; missing concrete entity → fail closed)
→ Investigation planner builds deterministic tool plan
→ Read-only tools execute: risk, behavior, alerts, personnel, timeline, relationship, search, dashboard, report, resolve_entity
→ Evidence validation + context builder
→ LLM explains grounded context only (citations / confidence)
→ Structured investigation report + saved cases + workflow panel + evidence drawer

AI PROVIDERS / CONTROL CENTER
- Chat providers: openrouter | ollama | lmstudio | openai_compatible | local(=ollama)
- Embeddings can differ from chat (e.g. OpenRouter chat + local nomic-embed-text)
- Vector backend: mongodb (ai_embeddings)
- Control Center: provider/model pick, generation params, cache clear, provider test, prompt reload
- Security: ReadOnlyPolicy — AI never mutates risk scores, alerts, or evidence stores
- LIVE vs SIMULATION memory/environment isolation

SIMULATION MODE (console-wide)
- Mode API: GET/PUT /api/mode, POST /api/mode/end
- Isolated Mongo: telegram_scraper_simulation (configurable)
- Same UI pages as live; Simulation banner
- Generate AI/fallback dummy messages; multi-select scenarios (narcotics, firearms, human_trafficking)
- Volume presets e.g. 24 / 48 / 80
- After generate: personnel rebuild, behavioral rebuild, embedding index for Sébastien
- Scrape jobs reclaim stuck generates; mode persisted

SIMULATOR LAB PAGE
- Isolated /api/simulator/*
- Widgets: overview, sessions, scenarios, personas, groups, live activity, pipeline inspector, benchmarks, reports, configuration
- Internal testing lab — production Mongo untouched by simulator console package

EVALUATION / BENCHMARKING
- Isolated evaluation/ + /api/evaluation/*
- Evaluators: keyword, risk, behavior, relationship, alert, pipeline, Sébastien
- Intelligence Quality Score (IQS), history, regression compare, leaderboard
- Ground truth hidden from sim UI; used only inside evaluation

SETTINGS (shared)
- Dark/light theme
- Telegram API ID / Hash / phone
- OpenRouter key (saving can auto-enable AI_ENABLED + provider wiring)
- Persisted to .env via /api/settings/env

OPS / DEPLOY
- dashboard.bat → FastAPI + Next.js
- mongo.bat → Docker Mongo
- auth / discover / scrape / extract / analytics / export / clear / auto-update
- Scrape limits: 100 / 500 / 1000 (live)
- Vercel hosts Next.js read-only from export.json (no Telethon/Mongo on Vercel)

════════════════════════════════════
SLIDE OUTLINE (24)
════════════════════════════════════

1. TITLE — Threat Console + subtitle (Sébastien · Live + Simulation · keyword OSINT)
2. PROBLEM — noisy Telegram threat chatter; analyst overload; need live ops + safe training data
3. SOLUTION — authorized collect → enrich → monitor → analyze → investigate → simulate → validate
4. FEATURE MAP — table of seven pillars with 2–4 capabilities each
5. ARCHITECTURE DIAGRAM — Telethon → keyword scrape jobs → Mongo (live | sim) → FastAPI routers → Next.js console (+ Sébastien / Behavioral / Simulator / Evaluation)
6. COLLECTION SPECS — Telethon auth/session, chat discovery, keyword-only storage, scrape limits 100/500/1000, dashboard scrape control, auto-update loop, optional demo bot
7. KEYWORD + RISK SPECS — 3 categories; stored fields (risk_score/level/factors, hits, sender, chat, media); why filter-at-ingest matters
8. ENTITY EXTRACTION SPECS — full entity type list; what downstream features consume them
9. CONSOLE SHELL — nav groups + Live⇄Sim toggle + scope + theme; list every page/route
10. DASHBOARD FUNCTIONALITY — KPIs, charts, scrape/generate, scope filters (detail the filter controls)
11. THREAT MONITORING — flagged feed, category/risk filters, keyword badges
12. ALERTS — Telegram alert rules + simulation local logging behavior
13. CHANNELS & USERS — sources list; personnel dossiers + rebuild API
14. ANALYTICS — chart types + CLI/HTML export path
15. BEHAVIORAL ANALYTICS — isolation model, profile signals, soft scoring, rebuild endpoint, UI route
16. SÉBASTIEN OVERVIEW — “investigation coordinator not chatbot”; pipeline steps as numbered list
17. SÉBASTIEN FUNCTIONALITY — intents, entity gate, tool list, citations/confidence, cases, Control Center
18. AI PROVIDERS & GUARDRAILS — provider matrix, embeddings/RAG, ReadOnlyPolicy, env isolation LIVE/SIM
19. SIMULATION MODE SPECS — DB isolation table, multi-scenario generate, volumes, post-generate rebuild/index, mode API
20. SIMULATOR LAB + EVALUATION — lab widgets + IQS/benchmark evaluators (two-column or split bullets)
21. SETTINGS & OPS — settings fields; bat scripts; Vercel read-only note
22. TECH STACK TABLE — collection / store / API / UI / AI / quality
23. 2-MINUTE DEMO PATH — 6 numbered steps (live → monitoring → behavioral → Sébastien → switch sim → generate → Sébastien on persona)
24. CLOSE — tagline Collect → Enrich → Monitor → Analyze → Investigate → Simulate → Validate + “Questions?”

RULES
- Do not invent integrations (no Slack/Jira/MITRE unless listed as future only — do not put future items on feature slides)
- Prefer concrete nouns: endpoint names, DB names, tool names, category names, ports
- Keep bullets ≤ 8 words when possible; use tables for matrices
- Professional threat-intel tone suitable for technical demos
```
