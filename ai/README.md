# AI Module (Scaffold)

Independent AI package for the Telegram Intelligence Platform.

This package is **opt-in and isolated**. It does not modify scrape, risk scoring,
alerting, existing FastAPI routes, or the Threat Console dashboard.

## Status

**Phase 10 — Isolated FastAPI router (`/api/ai`) + Sébastien UI (`/ai`)**

- Additive routes only: ``POST /query|/summary|/report|/investigate|/chat``, ``GET /health``
- Routes talk solely to ``AIServiceFacade`` (RAG / assistant / reports)
- Never exposes database sessions or raw Mongo documents
- Threat Console sidebar adds **Sébastien** → isolated ``/ai`` page (chat, investigate, search, reports, evidence)
- Existing dashboard pages unchanged beyond the menu entry

Prior phases remain available.

## Enable / disable

| Action | Effect |
|--------|--------|
| Leave unused | Health reports ``disabled`` / ``not_ready``; POSTs return 503 |
| Set `AI_*` + enable | `/api/ai/*` serves RAG, assistant, and reports |
| Delete / ignore `ai/` | Remove the single `include_router` line in `server.py` |

## Package layout

```text
ai/
├── config.py              # AI_* environment configuration
├── models/                # Internal DTOs / schemas
├── providers/             # LLM + embedding provider interfaces & stubs
├── prompts/               # Versioned Markdown templates + PromptLoader
├── embeddings/            # Embedding service + chunking (stubs)
├── vectorstore/           # Vector search backends (stubs)
├── llm/                   # LLM client helpers (stubs)
├── rag/                   # RAG engine (stubs)
├── extraction/            # Supplemental AI NER (stubs)
├── reports/               # Structured RAG reports + Markdown/HTML export
├── investigation/         # Multi-turn Investigation Assistant (RAG-only)
├── jobs/                  # Async index / entity workers
└── api/                   # FastAPI router mounted at /api/ai
```

## Module summary

| Path | Role |
|------|------|
| `config.py` | Load and validate `AI_*` settings; no Telegram/Mongo app config |
| `models/schemas.py` | Shared dataclasses / TypedDicts for AI artifacts |
| `providers/base.py` | `ChatModelProvider` (`chat`, `health_check`, `list_models`, `stream_chat`), `EmbeddingProvider` |
| `providers/errors.py` | Centralized `ProviderError` hierarchy |
| `providers/transport.py` | Internal HTTP JSON helper (private) |
| `providers/retry.py` | Exponential backoff retries |
| `providers/ollama.py` | Ollama chat + embeddings |
| `providers/openrouter.py` | OpenRouter (OpenAI-compatible) |
| `providers/lmstudio.py` | LM Studio local server |
| `providers/openai_compatible.py` | Generic OpenAI-compatible HTTP adapter |
| `providers/local.py` | Alias: `local` → Ollama (backward compatible) |
| `providers/factory.py` | `ProviderFactory.create(name)` from `AI_*` settings |
| `providers/models.py` | Normalized `DiscoveredModel` / capability metadata |
| `providers/cache.py` | TTL cache for model lists and provider health |
| `providers/discovery.py` | Dynamic model discovery (provider-agnostic) |
| `providers/registry.py` | Central `ModelRegistry` — no hardcoded model names |
| `prompts/` | Versioned Markdown templates + `PromptLoader` |
| `prompts/templates/` | Includes ``structured_report``, ``case_report``, ``rag_answer``, … |
| `embeddings/` | Chunking, hashing, batch embed, Mongo `ai_embeddings` repo |
| `jobs/indexer.py` | Async/sync flagged-message indexing job |
| `vectorstore/` | `VectorStore` + Qdrant / memory backends (no UI) |
| `llm/` | Completion client / JSON-mode stubs |
| `rag/` | RAG pipeline: retrieve → hydrate → prompt → generate |
| `extraction/` | AI NER + merge + ``ai_entities`` repository (async job) |
| `reports/` | Structured RAG reports + ``ai_reports`` + Markdown/HTML export |
| `investigation/` | Multi-turn Investigation Assistant (RAG-only, ``ai_sessions``) |
| `jobs/` | Indexer / entity extraction / CLI runner |
| `api/routes.py` | Isolated ``/api/ai`` router (facade only — no DB in handlers) |

### AI Control Center (Phase 3)

Sebastian’s header **Settings** button opens a side drawer (investigation stays visible).
Sections: General · Model · Generation · Performance · Advanced · About.

Additive control endpoints (configuration only — no intel mutation):

- `POST /api/ai/cache/clear`
- `POST /api/ai/provider/test`
- `POST /api/ai/prompts/reload`

Provider/model switches never clear conversations, evidence, or saved cases.

### Investigation Planner (Phase 5)

Sébastien is an **Investigation Coordinator**, not a chatbot:

```
User → Intent → InvestigationPlanner → ExecutionPlan → ToolRegistry
  → Evidence Validation → Context Builder → LLM Explain → Response
```

The LLM never queries Mongo or selects tools. Additive endpoints:

- `GET /api/ai/planner` (optional `?question=` plan preview)
- `GET /api/ai/tools`
- `POST /api/ai/investigate` (unchanged path; additive `deselected_tools`)

## Configuration

All settings use the `AI_` prefix. See `config.py` and `.env` examples in that module’s docstring.

Examples:

```text
AI_ENABLED=true
AI_CHAT_PROVIDER=ollama          # or: openrouter | lmstudio | openai_compatible | local
AI_CHAT_MODEL=                    # required — provider model id / Ollama tag
AI_EMBEDDING_PROVIDER=ollama
AI_EMBEDDING_MODEL=               # required — embedding model id
AI_API_BASE_URL=http://127.0.0.1:11434
AI_API_KEY=                       # required for OpenRouter; optional for LM Studio
AI_REQUEST_TIMEOUT_SECONDS=60
AI_RETRY_MAX_ATTEMPTS=3
AI_RETRY_BACKOFF_SECONDS=0.5
AI_MAX_TOKENS=2048
AI_MODEL_CACHE_TTL_SECONDS=300
```

Model names are never hardcoded. Discovery queries the active provider via
``GET /api/ai/models`` (and Sebastian’s provider/model dropdowns). Set a default
via ``AI_CHAT_MODEL`` or select a discovered model in the UI.

### Provider usage (ai package only — Sebastian uses the factory)

```python
from ai.config import load_ai_settings
from ai.providers import ChatMessage, ProviderFactory
from ai.providers.registry import get_model_registry

settings = load_ai_settings()
factory = ProviderFactory(settings)
chat = factory.create()  # or factory.create("openrouter") / create_chat_provider()
# result = chat.chat([ChatMessage(role="user", content="ping")])
# complete() remains for LLMClient / RAG compatibility
# health = chat.health_check(); models = chat.list_models()
# Discovery without requiring AI_CHAT_MODEL:
# discovery = factory.create_for_discovery("ollama")
# registry = get_model_registry(settings)
# registry.available_models("ollama", refresh=True)
```

Additive discovery HTTP endpoints (do not replace existing `/api/ai/*`):

- `GET /api/ai/providers`
- `GET /api/ai/models?provider=&refresh=`
- `GET /api/ai/provider/health?provider=&refresh=`

Do **not** import Ollama URLs or `ai.providers.transport` from application modules.

### Prompt usage (no model calls)

```python
from ai.prompts import PromptLoader

loader = PromptLoader()
rendered = loader.render(
    "case_report",
    case_title="Case 42",
    case_id="42",
    analyst_notes="…",
    subject_profiles="…",
    evidence_block="…",
    timeline_block="…",
)
# rendered.text  → ready for a later LLM phase
```

Override template root with `AI_PROMPTS_DIR` if needed.

### Embedding index job (out-of-band)

```text
AI_ENABLED=true
AI_EMBEDDING_PROVIDER=local
AI_EMBEDDING_MODEL=<ollama-embed-tag>
AI_EMBED_BATCH_SIZE=32
AI_CHUNK_MAX_CHARS=1200
AI_CHUNK_OVERLAP_CHARS=150
```

```bash
# Synchronous worker (separate process from scrape)
python -m ai.jobs.runner index_embeddings

# Queue on a daemon thread and return immediately
python -m ai.jobs.runner index_embeddings --async
```

Writes only to `ai_embeddings`, `ai_jobs`, and `ai_index_state`.

### Vector store (independent of embedding jobs)

```text
AI_VECTOR_BACKEND=qdrant
AI_VECTOR_URL=http://127.0.0.1:6333
AI_VECTOR_COLLECTION=ai_embeddings
```

```python
from ai.vectorstore import VectorPoint, create_vector_store

store = create_vector_store()
store.ensure_ready(dimension=384)
store.upsert([VectorPoint(id="msg:1", vector=[...], payload={"chat_id": 1})])
hits = store.search(query_vector, top_k=5, filters={"chat_id": 1})
```

Use `AI_VECTOR_BACKEND=memory` for local tests without Qdrant.

### RAG engine (no UI)

```text
AI_ENABLED=true
AI_CHAT_PROVIDER=local
AI_CHAT_MODEL=<chat-tag>
AI_EMBEDDING_PROVIDER=local
AI_EMBEDDING_MODEL=<embed-tag>
AI_VECTOR_BACKEND=qdrant   # or memory
AI_RAG_TOP_K=8
AI_RAG_MAX_EVIDENCE_ITEMS=8
AI_RAG_MAX_CONTEXT_CHARS=12000
AI_RAG_CONTEXT_TOKEN_BUDGET=3000
AI_MAX_TOKENS=2048
```

```python
from ai.models.schemas import QueryRequest
from ai.rag import RAGPipeline

pipeline = RAGPipeline.from_settings(db=mongo_db)
result = pipeline.run(QueryRequest(question="Who spiked overnight?"))
# result.answer, result.citations, result.confidence, result.retrieved, result.evidence
```

Mongo is used only by `MongoEvidenceLoader` to enrich vector hits. The chat model
receives assembled text — never a database handle.

### AI entity extraction (async, non-destructive)

```text
AI_ENABLED=true
AI_CHAT_PROVIDER=local
AI_CHAT_MODEL=<chat-tag>
AI_ENTITY_MIN_CONFIDENCE=0.4
AI_ENTITY_BATCH_SIZE=50
```

```bash
python -m ai.jobs.runner extract_entities
python -m ai.jobs.runner extract_entities --async
```

- Reads regex rows from ``extracted_entities`` for merge hints only
- Never updates/deletes ``extracted_entities``
- Writes only to ``ai_entities`` (confidence + ``matched_regex`` flag)

### Investigation Assistant (RAG-only, multi-turn)

```text
AI_ASSISTANT_NAME=Sébastien
AI_ASSISTANT_HISTORY_TURNS=8
AI_ASSISTANT_SESSION_COLLECTION=ai_sessions
```

```python
from ai.investigation import InvestigationAssistant

assistant = InvestigationAssistant.from_settings(db=mongo_db, subject={"user_id": 55})
turn = assistant.ask("Why is this user high risk?")
# turn.answer, turn.citations, turn.intent, turn.refused, turn.session_id

turn2 = assistant.ask("Show behavioral anomalies")  # same session
```

- Answers only via ``RAGPipeline`` (no free-form invention)
- Supported intents: high risk, summary, relationship, behavioral anomalies, timeline
- Session history is conversational context only — not treated as evidence
- Writes only to ``ai_sessions`` (never ``messages`` / ``user_activity`` / etc.)

### AI report generation (structured, RAG-grounded)

```text
AI_REPORT_COLLECTION=ai_reports
```

```python
from ai.reports import ReportExporter, ReportGenerator, ReportType

gen = ReportGenerator.from_settings(db=mongo_db)
report = gen.generate_user_intelligence(55)
# also: generate_investigation, generate_case_summary, generate_behavioral_analysis
# report.sections, report.citations, report.body_markdown, report.refused

exporter = ReportExporter()
exporter.export_markdown(report, Path("exports/ai/user-55.md"))
exporter.export_html(report, Path("exports/ai/user-55.html"))
# exporter.export_pdf(...)  → NotImplementedError until a later phase
```

- Four report types with fixed section catalogs
- Evidence retrieved via RAG; refuses when nothing is retrieved (no invented facts)
- Persists only to ``ai_reports``

### HTTP API (``/api/ai``)

Mounted additively from ``server.py`` via ``app.include_router(build_ai_router())``.
Handlers call ``AIServiceFacade`` only — never ``get_session`` / raw Mongo.

| Method | Path | Role |
|--------|------|------|
| GET | `/api/ai/health` | Config readiness (no model call) |
| POST | `/api/ai/query` | RAG Q&A |
| POST | `/api/ai/summary` | Subject summary (assistant / RAG) |
| POST | `/api/ai/report` | Structured report generation |
| POST | `/api/ai/investigate` | Investigation assistant turn |
| POST | `/api/ai/chat` | Multi-turn assistant chat |

```bash
curl -s http://127.0.0.1:8501/api/ai/health
curl -s -X POST http://127.0.0.1:8501/api/ai/query \
  -H "Content-Type: application/json" \
  -d '{"question":"Who spiked overnight?"}'
```

Requires ``AI_ENABLED=true`` plus chat, embedding, and vector backend settings.
POSTs return **503** when AI is not ready.

## Communication with the existing backend (future)

```text
Mongo core collections  ──read-only──►  ai/ jobs + RAG
                                              │
                                              ▼
                                       ai_* collections / vector DB
                                              │
                                              ▼
                               (later) additive /api/ai/* only
```

Phase 3 does **not** call models or register FastAPI routes.

## Extending in later phases

1. Implement OpenAI-compatible provider (optional).
2. Wire `/api/ai` into Threat Console UI via proxy pages (optional).
3. PDF export backend for `ReportExporter.export_pdf`.
4. Batch report job over personnel / cases.

## Safety rules

- Do not call LLMs from `message_scraper`, risk, or alert paths.
- Do not write to core collections (`messages`, `users`, `chats`, etc.).
- Do not change existing API contracts.
