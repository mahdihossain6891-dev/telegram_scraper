# Telegram Threat Console

**Intel-mining bot + risk assessment tool**

Authorized OSINT for Telegram groups & channels you already access.

---

## What it is

Two jobs, one pipeline:

### Intel mining bot
- Logs into Telegram with a persistent session
- Watches selected groups and channels
- Keeps only messages that hit **narcotics**, **human trafficking**, or **firearms** keywords
- Extracts phones, emails, URLs, domains, mentions, and hashtags

### Risk assessment tool
- Scores each **message**, **person**, and **channel**
- Levels: **Low → Medium → High → Critical**
- Uses keyword severity **plus behavioral patterns**

**Filter noise → Extract artifacts → Rank who to review**

---

## How it works (layer by layer)

| Layer | Bot action | Why it matters |
|-------|------------|----------------|
| **Access** | Auth + list chats | One trusted Telegram session |
| **Collect** | Keyword-gated scrape | Signal only — not the whole chat |
| **Store** | MongoDB documents | Live profiles for people & sources |
| **Enrich** | Entities + risk scores | Evidence + priority in one place |
| **Deliver** | Console + CSV/JSON | Briefings, cases, shareable reports |

Built phase by phase: CLI scrape → analytics → dashboard → **Next.js Threat Console** with live MongoDB.

---

## Risk assessment: behavior, not one keyword

Keywords find the hit. **Behavior** decides if it is a priority case.

| Pattern | Meaning | Score boost |
|---------|---------|-------------|
| 3+ flagged posts | Sustained activity | +20 |
| Seen in 2+ groups | Cross-community actor | +30 |
| Account ≤14 days old | Possible burner | +15 |
| 2+ threat categories in one thread | Broader illicit mix | +15 |
| Heavy phrases (e.g. trafficking, fentanyl) | High-severity content | up to ~50 |

> Scores prioritize investigation. They do **not** prove guilt.

---

## What operators get

### From the bot
- Flagged message archive
- Extracted contacts and links
- Per-person activity rollups
- Day-by-day suspect timelines

### From the risk tool
- Ranked cases (who to review first)
- Channel / source posture
- Command briefing KPIs
- CSV / JSON packs for Excel or a read-only shared dashboard

---

## One-line pitch

**A Telegram intel-mining bot with a built-in risk engine** — filter criminal-interest traffic, score behavior, hand analysts a ranked case list.

---

## Analyst console (at a glance)

| Area | Page | Job |
|------|------|-----|
| Investigate | Command | Live threat posture |
| Investigate | Cases | Person-centric suspects |
| Investigate | Intel | Message & entity evidence |
| Collect | Sources | Monitored chats |
| Analyze | Analytics | Timing & category depth |
| Operate | Ops | Live refresh & alerts |

**Local:** live MongoDB + FastAPI + Next.js  
**Share:** read-only export on Vercel (no credentials exposed)

---

## Guardrails

- Authorized data only (public channels / groups you can already access)
- Credentials and sessions stay local
- Cloud dashboard is read-only export data
- Human review required before any operational decision
