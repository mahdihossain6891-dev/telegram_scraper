# ADR 001: AI Integration Architecture

| Field | Value |
|--------|--------|
| **Status** | Proposed |
| **Date** | 2026-07-19 |
| **Deciders** | Platform maintainers |
| **Scope** | Telegram Intelligence Platform (Threat Console + scraper + FastAPI + MongoDB) |
| **Related** | [Behavioral Analytics isolation](../BEHAVIORAL_ANALYTICS.md) (reference pattern) |

## Context

The platform today is a **rule-based OSINT pipeline**:

```
Telegram (Telethon)
  → keyword-gated scrape (`message_scraper.py`)
  → MongoDB (`messages`, `users`, `chats`, `extracted_entities`, `user_activity`, …)
  → deterministic risk (`risk_scoring.py`) + personnel rollups (`personnel.py`)
  → optional Telegram alerts (`telegram_alerts.py`)
  → FastAPI (`server.py` :8501) → Next.js Threat Console (`web/` :3000)
  → optional export JSON for read-only Vercel hosting
```

Intelligence is currently produced by:

- **Keyword gates** (`keyword_filter.py`) — only matching messages are stored
- **Regex entities** (`entity_extractor.py`) — URLs, phones, mentions, etc.
- **Deterministic risk scores** (`risk_scoring.py`) — phrase weights + heuristics
- **Personnel activity** (`personnel.py`) — per-user rollups
- **Behavioral Analytics** (`behavioral_analytics.py`) — isolated statistical behavior profiles

There is **no LLM, embedding, or RAG stack** in the repository today. Adding AI must follow the same isolation contract already used by Behavioral Analytics: new module, new storage, new API surface, optional UI — without changing scrape latency, alert semantics, or existing dashboard contracts.

## Decision

We will integrate AI as an **isolated enrichment and retrieval layer** beside the existing deterministic pipeline:

1. Keep scrape → keyword → risk → alerts **synchronous and non-AI**.
2. Introduce a separate **AI service** that reads platform data (and optional knowledge corpora) and writes AI artifacts to dedicated collections / APIs.
3. Use **RAG (Retrieval-Augmented Generation)** for analyst-facing Q&A, case briefs, and evidence-grounded summaries.
4. Expose AI through additive FastAPI routes (e.g. `/api/ai/*`) and optional Next.js pages/proxies, mirroring `/api/behavioral/*` and `/behavioral-analytics`.

This ADR defines architecture and boundaries only; it does not mandate a specific vendor model.

---

## Goals

1. **Enrich, don’t replace** — AI should explain, summarize, and retrieve over existing flagged messages, entities, personnel, and behavioral profiles; it must not replace keyword gating or deterministic risk as the system of record for alerting.
2. **Grounded answers** — Analyst outputs (summaries, case narratives, “why is this user suspicious?”) must cite retrieved evidence (message IDs, chat IDs, entity hits, behavior alerts).
3. **Isolation** — AI must be enable/disable-able without breaking Command, Cases, Intel, Sources, Analytics, Ops, scrape, export, or Behavioral Analytics.
4. **Non-blocking collection** — Embedding, indexing, and inference must run asynchronously; Telethon scrape and `auto_update` loops must not wait on model calls.
5. **Swappable models** — Provider, model ID, and embedding model must be configurable behind a stable internal interface.
6. **Security & compliance posture** — Secrets stay in env; PII/OSINT data must not be logged carelessly; cloud vs local inference choices remain explicit.
7. **Fit existing ops model** — Local FastAPI + MongoDB remains the live path; Vercel remains read-only unless a separate hosted AI API is provisioned later.

## Non-goals

1. Replacing keyword filtering with an LLM classifier on the scrape hot path.
2. Storing full chat history solely to feed an LLM (corpus remains keyword-gated unless a future ADR expands collection policy).
3. Mutating schemas of `messages`, `users`, `chats`, `extracted_entities`, or `user_activity` as a prerequisite for AI.
4. Changing Telegram alert rules to fire on LLM-only confidence without human-reviewed policy.
5. Shipping a multi-tenant SaaS AI product in phase 1.
6. Fine-tuning custom foundation models as a day-one requirement (prompting + RAG first; fine-tuning is a later option).
7. Making the Vercel static export capable of private-key LLM calls without a dedicated backend.

---

## Proposed architecture

### High-level

```
┌──────────────────────────────────────────────────────────────────────┐
│ Existing platform (unchanged contracts)                              │
│  Scraper → MongoDB core collections → risk/personnel/alerts          │
│  FastAPI /api/data|/api/personnel|/api/behavioral|/api/alerts        │
│  Next.js Threat Console + Behavioral Analytics page                  │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ read-only (or copy-on-read)
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ AI Service (new process or in-process package with hard boundaries)  │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │ Ingest/Index│→│ Vector store │→│ Retriever   │→│ Generator  │ │
│  │ (async jobs)│  │ (embeddings) │  │ (RAG)       │  │ (LLM)      │ │
│  └─────────────┘  └──────────────┘  └─────────────┘  └────────────┘ │
│  ModelProvider interface (OpenAI / Azure / local / future)           │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ writes AI artifacts only
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ AI storage (dedicated)                                               │
│  ai_documents · ai_embeddings · ai_jobs · ai_insights · ai_sessions  │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Additive API + optional UI                                           │
│  FastAPI /api/ai/*  →  Next proxy  →  optional /ai or Case panels    │
└──────────────────────────────────────────────────────────────────────┘
```

### Core components

| Component | Responsibility |
|-----------|----------------|
| **AI Ingestor** | Watches or batch-reads flagged messages, entities, personnel, behavioral profiles; normalizes into `ai_documents` chunks |
| **Embedder** | Produces vectors via `EmbeddingProvider`; upserts into vector index |
| **Retriever** | Hybrid retrieval (vector + optional metadata filters: chat_id, user_id, date, category, risk/behavior score) |
| **Generator** | Builds grounded prompts; calls `ChatModelProvider`; returns answer + citations |
| **Insight Writer** | Persists structured insights (case brief, user narrative, anomaly explanation) to `ai_insights` |
| **Job Runner** | Async queue/scheduler for index rebuild, re-embed, insight generation — never inside Telethon message loop |
| **API Facade** | Thin FastAPI adapters under `/api/ai/*` that call the AI service; no scrape coupling |

### Reference isolation pattern

Behavioral Analytics already proved the preferred extension style:

- Own Python module + own Mongo collection
- Own `/api/behavioral/*` routes
- Own Next page + proxy
- Rebuild/read path that does not write core collections

AI should follow the same pattern with stricter process separation for model I/O (timeouts, retries, cost controls).

---

## Module boundaries

### Inside AI boundary (new)

- `ai/` (or `services/ai/`) package: providers, chunking, retrieval, prompting, jobs
- Mongo collections prefixed `ai_*` (or a separate DB name if ops prefer full isolation)
- FastAPI router mounted only under `/api/ai`
- Optional Next routes under `/ai` or Case-side panels that call AI proxies only
- Config keys prefixed `AI_` / `LLM_` / `EMBEDDING_` in `.env`

### Outside AI boundary (must not own)

| Module | Rule |
|--------|------|
| `message_scraper.py` | No LLM/embed calls; may enqueue a lightweight job ID at most |
| `keyword_filter.py` / `risk_scoring.py` / `telegram_alerts.py` | Remain deterministic systems of record |
| `personnel.py` / `behavioral_analytics.py` | AI may **read**; must not require their schema changes |
| `exporter.py` / `GET /api/data` | Export payload shape stays stable unless a versioned optional `ai` section is explicitly added later |
| Telethon session / `.env` Telegram secrets | Never sent to model providers beyond redacted/allowed fields |

### Allowed read dependencies

AI may read:

- `messages`, `extracted_entities`, `users`, `chats`
- `user_activity`, `behavioral_analytics`
- Optional curated playbooks / SOP markdown (operator-provided knowledge base)

AI may write only:

- `ai_documents`, `ai_embeddings` (or external vector DB), `ai_jobs`, `ai_insights`, `ai_sessions` (chat history for analysts)

---

## Data flow

### A. Offline / scheduled indexing

```
1. Job: ai.index_incremental
2. Read new/updated flagged messages (+ entities, optional behavior alerts)
3. Chunk → embed → upsert vectors + metadata (user_id, chat_id, ts, risk, categories)
4. Mark job complete; metrics: docs indexed, tokens, latency
```

### B. Analyst Q&A (RAG)

```
1. UI → POST /api/ai/query { question, filters, user_id? }
2. Retrieve top-k chunks (vector + filters)
3. Build prompt: system policy + retrieved evidence + question
4. Generate answer with citation IDs
5. Persist session turn to ai_sessions; return { answer, citations, model, latency }
```

### C. Case / user brief (batch insight)

```
1. UI or scheduler → POST /api/ai/insights/user/{id}
2. Retrieve evidence for that user (messages, entities, behavior alerts, risk factors)
3. Generate structured brief (JSON schema)
4. Store in ai_insights; UI displays without blocking scrape
```

### D. What never happens on the hot path

```
Telethon message received
  → keyword match?
  → persist + risk + personnel + alert
  ✗ no await llm.complete()
  ✗ no await embed()
```

Optional later: fire-and-forget enqueue to a job queue after persist.

---

## Why RAG is used

| Problem without RAG | RAG mitigation |
|---------------------|----------------|
| LLM invents chat titles, users, or threat links | Answers constrained to retrieved Mongo-backed evidence |
| Platform data changes daily | Index increments; retrieval always reflects current corpus |
| Model weights cannot hold private OSINT | Private evidence stays in our DB/vector store; model only sees retrieved slices |
| Analysts need provenance | Citations (message/chat/user IDs) are first-class |
| Keyword corpus is sparse but high-signal | RAG over flagged messages is cheaper and more relevant than unrestricted chat dumps |
| Multiple artifact types (text, entities, behavior events) | Chunks + metadata filters unify heterogeneous sources |

RAG is chosen over “stuff entire export into the prompt” because the corpus will grow to thousands of users and messages; retrieval keeps context windows, cost, and latency bounded.

Pure fine-tuning is deferred: it does not solve freshness or citation, and is expensive relative to RAG over an already structured Mongo corpus.

---

## Why the AI service is separate

1. **Failure isolation** — Provider outages, rate limits, or prompt bugs must not take down scrape, alerts, or `/api/data`.
2. **Performance isolation** — Embedding and generation are CPU/GPU/network heavy; scrape and dashboard reads stay snappy.
3. **Security boundary** — Easier to audit what leaves the trust boundary (redaction, allowlists, DLP hooks) in one service.
4. **Cost control** — Quotas, caching, and model tiering live in one place.
5. **Deploy flexibility** — Local-only AI, remote API, or hybrid; Vercel frontend can stay static while AI stays on the FastAPI host (or a later dedicated worker).
6. **Parity with Behavioral Analytics** — Optional capability: disable AI by not mounting routes / stopping the worker; core SOC features remain.

“Separate” means a **hard module boundary** and preferably a **separate process/worker** for jobs. Phase 1 may keep the package in-repo and invoke it from FastAPI, but must not share request threads with scrape loops.

---

## How future models can be swapped

### Provider interface (conceptual)

```text
ChatModelProvider
  complete(messages, tools?, json_schema?) → Completion

EmbeddingProvider
  embed(texts[]) → vectors[]

RerankProvider (optional)
  rerank(query, documents[]) → ranked[]
```

### Swap mechanisms

| Lever | Usage |
|-------|--------|
| **Env config** | `AI_CHAT_PROVIDER`, `AI_CHAT_MODEL`, `AI_EMBEDDING_PROVIDER`, `AI_EMBEDDING_MODEL`, base URLs, API keys |
| **Factory** | Single registry maps provider name → implementation (OpenAI-compatible, Azure OpenAI, Ollama/local, Anthropic, etc.) |
| **OpenAI-compatible HTTP** | Prefer providers exposing the same chat/embeddings HTTP shape to minimize adapters |
| **Versioned prompts** | Prompt templates versioned (`v1`, `v2`) independent of model ID |
| **Embedding migration jobs** | Changing embedding model triggers re-index job; store `embedding_model` on each vector record |
| **Feature flags** | Route traffic to a shadow model for eval without changing UI contracts |
| **Stable API DTOs** | `/api/ai/query` response shape stays constant; `model` field reports which backend answered |

### Compatibility rules

- Never persist provider-specific raw payloads as the only source of truth for insights; normalize to internal schemas.
- Citations and filters remain Mongo IDs, not vendor document IDs.
- Evaluation harness (golden questions + expected citation set) must pass before promoting a new default model.

---

## Risks and mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Hallucinations** | False investigative leads | Mandatory RAG citations; refuse when retrieval empty; UI shows evidence first |
| **Prompt injection via Telegram text** | Manipulated summaries/alerts | Treat message text as untrusted data; separate system vs untrusted content; no tool that can send alerts from model output in phase 1 |
| **PII leakage to cloud LLM** | Compliance / ToS | Redaction layer; local model option; data-processing agreement; field allowlists |
| **Scrape latency regression** | Missed collection windows | Hard ban on sync AI in scraper; async jobs only |
| **Alert spam from AI** | Operator fatigue | AI does not drive `telegram_alerts` unless a future ADR explicitly allows it |
| **Cost blowups** | Unexpected API spend | Per-day token budgets; cache identical queries; smaller models for embedding; batch insights |
| **Index drift** | Stale answers | Incremental indexer tied to message `_id` / `updated_at`; rebuild endpoint like behavioral |
| **Export / Vercel confusion** | AI “works locally” but not on static host | Document local-only; optional remote AI gateway later |
| **Schema coupling** | Breaking dashboards | AI writes only `ai_*` collections; optional UI only |
| **Over-trust of scores** | Operators treat LLM confidence as proof | Present AI as assistive; keep deterministic risk/behavior as primary badges |

---

## Scalability considerations

1. **Corpus size** — Start from keyword-flagged messages (already bounded). Chunk by message or small windows (reply threads), not entire chats.
2. **Vector store** — Phase 1: MongoDB vector search **or** a sidecar (e.g. Qdrant/Chroma) selected in implementation; store metadata for filtered search (user, chat, time, category).
3. **Indexing throughput** — Batch embeds (tens–hundreds of texts); backoff on 429; idempotent upserts by `source_type + source_id + chunk_id`.
4. **Query path** — Top-k small (e.g. 6–20); optional hybrid BM25/metadata prefilter; timeout budgets (e.g. 30s) with graceful degradation.
5. **Caching** — Cache embeddings for unchanged text hashes; cache insight briefs until source fingerprint changes.
6. **Horizontal scale** — Stateless API + worker consumers on a job queue; Mongo remains source of truth for OSINT; vector DB/replicas for retrieval scale.
7. **Multi-thousand users** — Prefer per-user insight generation on demand + LRU cache over nightly full regeneration of every profile.
8. **Observability** — Metrics: queue depth, embed latency, tokens in/out, retrieval hit rate, citation coverage, error rate by provider.

---

## Implementation phases

### Phase 0 — Foundations (no user-facing AI)

- Add `docs/adr/001-ai-architecture.md` (this document)
- Agree provider interface + `AI_*` env schema
- Create empty `ai_*` collection names / index plan (no change to core collections)
- Spike: embed 100 sample flagged messages; measure cost/latency

### Phase 1 — RAG MVP (local analyst assist)

- Implement `EmbeddingProvider` + `ChatModelProvider` (one cloud **or** one local backend)
- Async indexer job over `messages` + `extracted_entities`
- `POST /api/ai/query` with citations
- Minimal Next proxy + isolated page or Cases-side panel (additive only)
- Guardrails: empty-retrieval refusal, timeouts, token budget

### Phase 2 — Structured insights

- `POST /api/ai/insights/user/{id}` and chat/case briefs
- Pull behavioral alerts + risk factors into retrieval filters
- Persist `ai_insights`; show alongside (not instead of) deterministic scores
- Eval set: golden questions with expected message IDs

### Phase 3 — Hardening & scale

- Job queue worker process separate from uvicorn request workers
- Re-embed migration tooling; shadow model flag
- Redaction/PII policy; audit log of prompts/responses (retention-limited)
- Optional hybrid search + reranker
- Cost dashboards in Ops (read-only metrics)

### Phase 4 — Optional productization (separate ADRs)

- AI-assisted alert **drafts** (human approve before send)
- Multi-lingual investigation assistants
- Fine-tuned classifier as **secondary** signal (never sole alert trigger without policy ADR)
- Hosted AI gateway for non-local frontends

Each phase must preserve: scrape performance, alert determinism, `/api/data` compatibility, and Behavioral Analytics isolation.

---

## Consequences

### Positive

- Analysts get grounded natural-language investigation support without rewriting the OSINT core.
- Clear disable path and blast-radius limits.
- Model/vendor flexibility as the ecosystem changes.

### Negative / trade-offs

- Additional operational surface (keys, quotas, vector index, workers).
- Answers limited to what was collected (keyword-gated corpus).
- Local vs cloud trade-off between privacy and quality must be chosen per deployment.

### Follow-ups

- ADR 002 (when needed): vector store technology choice (MongoDB vs dedicated)
- ADR 003 (when needed): cloud data-handling / redaction policy
- ADR 004 (when needed): AI-assisted alerting policy

---

## Appendix: Alignment with current codebase

| Current asset | AI interaction |
|---------------|----------------|
| `server.py` | Add mountable `/api/ai` router only; do not alter existing route behavior |
| `database.py` | Add accessors for `ai_*` collections; do not change existing indexes’ semantics |
| `web/components/DashboardApp.tsx` | Optional nav link only (same pattern as Behavioral Analytics) |
| `behavioral_analytics.py` | Read-only enrichment source for RAG context |
| `auto_update.py` | May schedule AI index jobs after export; must not block scrape on LLM |
| Vercel export | Remains non-AI unless a remote AI API is explicitly configured |

---

## Decision summary

**Adopt an isolated, RAG-centric AI enrichment service** that reads the existing Mongo-backed intelligence corpus, writes only to dedicated AI collections, exposes additive APIs/UI, and keeps scrape, keyword risk, and alerting deterministic. Models are swapped behind provider interfaces and env configuration; rollout proceeds in phased MVPs with explicit non-goals around hot-path inference and schema mutation.
