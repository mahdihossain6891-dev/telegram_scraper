# Telegram Export JSON Format

Guide to `exports/export.json` produced by `export.bat` / `exporter.py`.

## Generate

```powershell
.\export.bat
```

Writes under `exports/`:

| File | Contents |
|------|----------|
| `export.json` | Full payload (dashboard + Vercel) |
| `chats.csv` | Channels / groups |
| `users.csv` | Senders |
| `messages.csv` | Flagged messages |
| `entities.csv` | Extracted entities |

## Top-level shape

```json
{
  "exported_at": "2026-07-28T16:17:15+06:00",
  "counts": {
    "chats": 4,
    "users": 4,
    "messages": 242,
    "entities": 520,
    "personnel": 4
  },
  "chats": [],
  "users": [],
  "messages": [],
  "entities": [],
  "personnel": []
}
```

## Field notes

### `chats[]`
`id`, `title`, `username`, `chat_type`, `risk_score`, `risk_level`, `risk_factors`, timestamps

### `users[]`
`id`, `username`, `first_name`, `last_name`, timestamps

### `messages[]`
`id`, `message_id`, `chat_id`, `sender_id`, `timestamp`, `text`, `media_type`,
`reply_to_message_id`, `forward_from_chat_id`, `risk_score`, `risk_level`, `risk_factors`

### `entities[]`
`id`, `message_row_id`, `entity_type`, `entity_value`, offsets

Common `entity_type` values: `url`, `domain`, `email`, `phone`, `mention`, `hashtag`,
`wallet`, `address`, plus keyword categories (`narcotics`, `human_trafficking`, `firearms`).

### `personnel[]`
Per-user activity rollups (message counts, suspicious counts, keywords, risk).

## Live vs static

| Mode | Source |
|------|--------|
| Local Threat Console | FastAPI `GET /api/data` (live Mongo) |
| Vercel demo | `web/public/data/export.json` (snapshot) |

## Related exports

| Script | Output |
|--------|--------|
| `.\maltego_export.bat` | Maltego relationship CSVs + GraphML under `exports/` |
| `.\analytics.bat` | Plotly HTML charts under `exports/` |
