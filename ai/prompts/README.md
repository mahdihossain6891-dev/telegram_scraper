# AI Prompt Templates

Prompts live **only** as Markdown files under `templates/`.

Python code must load them via ``PromptLoader`` — never embed prompt text
in ``.py`` files.

## Layout

```text
templates/
  <prompt_id>/
    v1.md
    v2.md   # optional later versions
```

## Naming

| Prompt ID | Purpose |
|-----------|---------|
| `message_classification` | Classify a Telegram message |
| `investigation_summary` | Summarize an investigation subject |
| `rag_answer` | Grounded RAG Q&A with citations |
| `case_report` | Structured case report (legacy prompt) |
| `investigation_assistant` | Multi-turn analyst assistant |
| `entity_extraction` | AI NER JSON extraction |
| `structured_report` | Sectioned RAG reports (Phase 9) |

## File format

Optional YAML front matter, then Markdown body. Variables use
``{{variable_name}}`` placeholders.

```markdown
---
id: example
version: v1
description: Short description
variables:
  - foo
  - bar
---

Body with {{foo}} and {{bar}}.
```

If `variables` is omitted, the loader infers placeholders from the body.
