# harness-playground API Contract

Backend base URL: `http://localhost:8000` (or configured host).

## Auth

All endpoints (except `/health`) require the `X-User-Id` header.
Auth/JWT verification is assumed to be done upstream (reverse-proxy / API gateway).
The harness only receives an already-verified user ID.

```
X-User-Id: alice
```

---

## Endpoints

### `GET /health`

Readiness probe. Returns `200` when the agent and Postgres (if enabled) are up.

```json
{"status": "ok", "postgres": "ok"}
```

---

### `POST /chat/stream`

Send a message and receive the agent's response as an SSE stream.

**Request (JSON body):**
```json
{
  "session_id": "main",
  "message": "summarize this codebase"
}
```

**Headers:** `X-User-Id: alice`

**Response:** `text/event-stream`

Each line is an SSE event:

```
event: message
data: {"type": "ai", "content": "Here is the summary..."}

event: tool_call
data: {"tool": "list_dir", "args": {"path": "."}}

event: tool_result
data: {"tool": "list_dir", "content": "d harness\nd skills\n..."}

event: interrupt
data: {"type": "approval", "tool": "run_bash", "args": {"command": "ls /"}}

event: done
data: {}
```

#### Slash commands

If `message` starts with `/`, it is dispatched as a slash command before reaching the agent:

```
/help               — list commands
/clear              — info on clearing a session
/list-skills        — show loaded skill sub-agents
```

Custom commands return `message` events directly (no agent loop).

---

### `POST /threads/{thread_id}/runs/resume`

Resume a run that was interrupted (e.g., awaiting HITL approval).

`thread_id` format: `{user_id}:{session_id}` (e.g., `alice:main`).

**Request (JSON body):**
```json
{"resume": "approve"}
```

`resume` must be `"approve"` or `"deny"`.

**Response:** Same SSE stream as `/chat/stream` — continues from where the interrupt paused.

#### HITL flow (frontend implementation guide)

1. Stream `/chat/stream` as normal.
2. On `event: interrupt`, render an approval dialog to the user.
   - `data` contains `{"type": "approval", "tool": "...", "args": {...}}`.
3. On user confirm/deny, POST to `/threads/{user}:{session}/runs/resume` with `{"resume": "approve" | "deny"}`.
4. Continue streaming the response from the resume endpoint.

---

### `GET /threads/{user_id}`

List all sessions for a user.

```json
{"sessions": ["main", "research", "demo"]}
```

---

### `GET /threads/{user_id}/{session_id}/messages`

Return the full message history for a session.

```json
{
  "messages": [
    {"type": "human", "content": "hello", "name": null},
    {"type": "ai", "content": "Hi there!", "name": null}
  ]
}
```

---

### `DELETE /threads/{user_id}/{session_id}`

Delete all checkpoints for a session (irreversible).

```json
{"deleted": true}
```

---

### `GET /commands`

Slash command metadata for frontend autocomplete.

```json
{
  "commands": [
    {"name": "help", "description": "List all available slash commands", "args": {}},
    {"name": "list-skills", "description": "List all loaded skill sub-agents", "args": {}}
  ]
}
```

---

### `GET /pipelines`

List registered pipelines with their JSON schemas.

```json
{
  "pipelines": [
    {
      "name": "summarize_text",
      "description": "Summarize text into a structured JSON report.",
      "input_schema": {...},
      "output_schema": {...}
    }
  ]
}
```

---

### `POST /api/{pipeline_name}`

Run a registered pipeline. Input body matches the pipeline's `input_schema`.

**Example — `summarize_text`:**

```http
POST /api/summarize_text
Content-Type: application/json

{"text": "Long article text here...", "language": "Vietnamese"}
```

```json
{
  "title": "Tiêu đề bài viết",
  "summary": "Tóm tắt trong 2-3 câu...",
  "key_points": ["Điểm 1", "Điểm 2"],
  "word_count": 450
}
```

---

## SSE Event Reference

| Event | When | Data shape |
|---|---|---|
| `message` | AI response text or tool calls | `{"type": "ai", "content": "...", "tool_calls"?: [...]}` |
| `tool_result` | Tool call completed | `{"tool": "...", "content": "..."}` |
| `interrupt` | Agent needs human approval | `{"type": "approval", "tool": "...", "args": {...}}` |
| `done` | Stream finished | `{}` |
| `error` | Unhandled exception | `{"message": "..."}` |

---

## Error responses

Standard HTTP errors for non-stream endpoints:

| Code | Meaning |
|---|---|
| 401 | `X-User-Id` header missing |
| 404 | Pipeline or resource not found |
| 500 | Internal server error |

---

## Open integration TODOs

- **JWT verification**: currently assumes `X-User-Id` is pre-verified at the gateway. To verify inside harness, add a FastAPI dependency that decodes the JWT and extracts `sub` → `user_id`.
- **File uploads**: multipart upload for `/chat/stream` (`attachments` field) — files are saved to `./uploads/` and passed to `analyze_image`. Not yet implemented.
- **Rate limiting**: handle at the gateway level, not in harness.
