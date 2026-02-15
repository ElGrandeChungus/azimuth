# BUILD SPEC: Personal AI Assistant — Phase 0 (v1.0)

> **Target agent**: AI IDE (Antigravity primary, portable to Windsurf/Claude Code)
> **Target timeline**: Single weekend session
> **Target platform**: Windows home server, Docker Desktop installed
> **Model provider**: OpenRouter (API key available)

---

## PROJECT OVERVIEW

Build a self-hosted personal AI chat assistant as a web app.
Two containers: Python backend (FastAPI) + React frontend (Vite).
SQLite for persistence. OpenRouter for AI model access.
Streaming responses via Server-Sent Events.
Mobile-responsive. Accessible from any device on local network.

**Project name**: `nexus` (working name — the personal AI hub)

---

## TECH STACK (Do not deviate)

| Layer | Technology | Version |
|-------|-----------|---------|
| Backend | Python + FastAPI | Python 3.12, FastAPI 0.115+ |
| Database | SQLite via aiosqlite | aiosqlite 0.20+ |
| AI API | OpenRouter (OpenAI-compatible) | openai SDK 1.50+ |
| Frontend | React + TypeScript + Vite | React 18, Vite 5 |
| Styling | Tailwind CSS | v3 |
| Deployment | Docker Compose | Compose v2 |

**Important constraints**:
- Use the `openai` Python SDK pointed at OpenRouter's base URL.
  OpenRouter is OpenAI-compatible. Do NOT write a custom HTTP client.
- Use `aiosqlite` for async database access. No ORMs (no SQLAlchemy).
- Frontend uses Tailwind utility classes only. No component library.
- All state management via React hooks. No Redux, no Zustand.

---

## FILE STRUCTURE

Create this exact structure. Do not add extra files or directories.

```
nexus/
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app, CORS, lifespan
│   │   ├── config.py               # Settings from env vars
│   │   ├── database.py             # SQLite init, connection, migrations
│   │   ├── models.py               # Pydantic request/response models
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── conversations.py    # CRUD for conversations
│   │   │   ├── messages.py         # Send message + stream AI response
│   │   │   └── settings.py         # Config + system prompts + models list
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── ai.py               # OpenRouter client (streaming)
│   │       └── prompts.py          # System prompt assembly
│   └── data/                        # SQLite DB lives here (volume mounted)
│       └── .gitkeep
│
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── index.css                # Tailwind directives
        ├── api/
        │   └── client.ts            # All API calls
        ├── components/
        │   ├── ChatView.tsx          # Main chat area
        │   ├── MessageList.tsx       # Scrollable message list
        │   ├── MessageBubble.tsx     # Single message display
        │   ├── MessageInput.tsx      # Text input + send button
        │   ├── Sidebar.tsx           # Conversation list + new chat
        │   ├── ModelSelector.tsx     # Model dropdown
        │   └── SettingsPanel.tsx     # API key, prompts, model default
        ├── hooks/
        │   ├── useChat.ts            # Conversation state + message sending
        │   └── useStream.ts          # SSE stream consumption
        └── types/
            └── index.ts              # TypeScript interfaces
```

---

## DATABASE SCHEMA

Single SQLite file at `backend/data/nexus.db`.
Create tables on startup if they don't exist.

```sql
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT 'New Conversation',
    model TEXT NOT NULL DEFAULT '',
    system_prompt_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (system_prompt_id) REFERENCES system_prompts(id)
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    model TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS system_prompts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    content TEXT NOT NULL,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Index for fast conversation message loading
CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id, created_at);

-- Index for conversation listing
CREATE INDEX IF NOT EXISTS idx_conversations_updated
    ON conversations(updated_at DESC);
```

**On first startup**, seed the database with:

```sql
-- Default system prompt
INSERT OR IGNORE INTO system_prompts (id, name, content, is_default)
VALUES (
    'default',
    'Default',
    'You are a helpful personal AI assistant. Be conversational, concise, and direct. If you do not know something, say so.',
    1
);

-- Default config
INSERT OR IGNORE INTO config (key, value) VALUES ('default_model', '"anthropic/claude-sonnet-4-20250514"');
INSERT OR IGNORE INTO config (key, value) VALUES ('theme', '"dark"');
```

---

## BACKEND SPECIFICATIONS

### app/config.py

Read from environment variables:

```python
OPENROUTER_API_KEY: str          # Required. No default.
OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
DATABASE_PATH: str = "data/nexus.db"
DEFAULT_MODEL: str = "anthropic/claude-sonnet-4-20250514"
CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]
```

Add the server's local IP to CORS_ORIGINS via env var so phone can connect.

### app/main.py

- FastAPI app with lifespan handler (init DB on startup)
- CORS middleware allowing configured origins
- Mount routers: conversations, messages, settings
- Health check at `GET /api/health`

### app/database.py

- `init_db()`: create tables + seed defaults (idempotent)
- `get_db()`: async context manager yielding aiosqlite connection
- All queries use parameterized statements (no f-strings)
- Enable WAL mode and foreign keys on every connection

### app/services/ai.py

Use the `openai` Python SDK with OpenRouter:

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.OPENROUTER_API_KEY,
)

async def stream_chat(messages: list[dict], model: str):
    """Yield content deltas from OpenRouter streaming response."""
    stream = await client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        extra_headers={
            "HTTP-Referer": "http://localhost:3000",
            "X-Title": "Nexus Assistant",
        },
    )
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
```

### app/routers/messages.py — THE CORE ENDPOINT

`POST /api/conversations/{conversation_id}/messages`

Request body: `{ "content": "user message text" }`

Behavior:
1. Save user message to DB
2. Load full message history for this conversation
3. Load the conversation's system prompt (or default)
4. Build messages array: [system, ...history, new_user_message]
5. Stream AI response via SSE
6. Accumulate full response text
7. Save assistant message to DB after stream completes
8. Update conversation.updated_at
9. If this is the first exchange, auto-generate title:
   Make a non-streaming call asking the model to summarize
   the first user message as a short title (5 words max)

SSE format (each event):
```
data: {"type": "delta", "content": "partial text"}

data: {"type": "done", "message_id": "uuid", "model": "anthropic/claude-sonnet-4-20250514"}
```

Error format:
```
data: {"type": "error", "message": "description of what went wrong"}
```

Response type: `text/event-stream`

### app/routers/conversations.py

Standard CRUD:

- `GET /api/conversations` — list all, ordered by updated_at DESC
  - Response: array of `{id, title, model, updated_at, message_count}`
  - Include message count via subquery
- `POST /api/conversations` — create new with optional model and system_prompt_id
  - Generate UUID for id
  - Return the new conversation object
- `GET /api/conversations/{id}` — get conversation with all messages
- `DELETE /api/conversations/{id}` — delete conversation and cascade messages
- `PATCH /api/conversations/{id}` — update title or model

### app/routers/settings.py

- `GET /api/settings` — return all config key-value pairs
- `PATCH /api/settings` — update one or more config values
- `GET /api/settings/models` — proxy to OpenRouter's model list endpoint
  Filter to text/chat models only. Cache for 1 hour.
- `GET /api/settings/prompts` — list all system prompts
- `POST /api/settings/prompts` — create new prompt
- `PATCH /api/settings/prompts/{id}` — update prompt
- `DELETE /api/settings/prompts/{id}` — delete (prevent deleting default)

### app/services/prompts.py

```python
async def build_messages(conversation_messages, system_prompt_content):
    """Assemble the messages array for the AI call."""
    messages = [{"role": "system", "content": system_prompt_content}]
    for msg in conversation_messages:
        messages.append({"role": msg["role"], "content": msg["content"]})
    return messages
```

### requirements.txt

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
aiosqlite==0.20.0
openai==1.58.1
pydantic==2.10.3
python-dotenv==1.0.1
```

### Backend Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/
COPY data/ data/
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## FRONTEND SPECIFICATIONS

### Core Behavior

- On load: fetch conversation list, select most recent (or show empty state)
- Selecting a conversation loads its messages
- Sending a message initiates SSE stream, displays tokens as they arrive
- New messages appear at bottom, auto-scroll during streaming
- Mobile: sidebar collapses to hamburger menu, chat view fills screen

### src/types/index.ts

```typescript
export interface Conversation {
  id: string;
  title: string;
  model: string;
  updated_at: string;
  message_count: number;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  model?: string;
  created_at: string;
}

export interface SystemPrompt {
  id: string;
  name: string;
  content: string;
  is_default: boolean;
}

export interface StreamEvent {
  type: 'delta' | 'done' | 'error';
  content?: string;
  message_id?: string;
  model?: string;
  message?: string;
}
```

### src/api/client.ts

All API calls go through this module. Base URL from env var `VITE_API_URL`
defaulting to `http://localhost:8000/api`.

Functions:
- `getConversations(): Promise<Conversation[]>`
- `createConversation(model?: string, systemPromptId?: string): Promise<Conversation>`
- `getConversation(id: string): Promise<{conversation: Conversation, messages: Message[]}>`
- `deleteConversation(id: string): Promise<void>`
- `updateConversation(id: string, updates: Partial<Conversation>): Promise<Conversation>`
- `sendMessage(conversationId: string, content: string): EventSource`
  Returns an EventSource. The hook handles parsing SSE events.
- `getSettings(): Promise<Record<string, any>>`
- `updateSettings(settings: Record<string, any>): Promise<void>`
- `getModels(): Promise<Array<{id: string, name: string}>>`
- `getSystemPrompts(): Promise<SystemPrompt[]>`
- `createSystemPrompt(name: string, content: string): Promise<SystemPrompt>`
- `updateSystemPrompt(id: string, updates: Partial<SystemPrompt>): Promise<SystemPrompt>`
- `deleteSystemPrompt(id: string): Promise<void>`

### src/hooks/useStream.ts

Custom hook that:
1. Takes a conversation ID and message content
2. Calls `sendMessage` which returns EventSource or uses fetch + ReadableStream
3. Parses SSE events into StreamEvent objects
4. Maintains state: `isStreaming`, `streamedContent`, `error`
5. On "done" event: returns final message info
6. On "error" event: sets error state
7. Cleanup: abort on unmount

**Implementation note**: Use `fetch()` with `ReadableStream` rather than
`EventSource` since EventSource doesn't support POST requests.

```typescript
const response = await fetch(`${API_URL}/conversations/${id}/messages`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ content }),
});
const reader = response.body!.getReader();
const decoder = new TextDecoder();
// Parse SSE lines from chunks
```

### src/hooks/useChat.ts

Manages conversation state:
- `conversations`: list of all conversations
- `activeConversation`: currently selected conversation
- `messages`: messages for active conversation
- `isStreaming`: whether AI is currently responding
- Functions: `selectConversation`, `createConversation`,
  `deleteConversation`, `sendMessage`, `refresh`

### Component Specifications

**App.tsx**: Layout shell. Sidebar on left (collapsible), chat view filling
remaining space. Settings as a modal/panel overlay.

**Sidebar.tsx**:
- "New Chat" button at top
- List of conversations showing title and relative timestamp
- Active conversation highlighted
- Click to select, show delete button on hover/long-press
- On mobile (< 768px): overlay that slides in from left

**ChatView.tsx**:
- Shows active conversation's messages via MessageList
- MessageInput fixed at bottom
- ModelSelector in top bar
- If no conversation selected: centered "Start a new conversation" prompt

**MessageList.tsx**:
- Scrollable container
- Auto-scrolls to bottom on new messages and during streaming
- Shows MessageBubble for each message

**MessageBubble.tsx**:
- User messages: right-aligned, colored background
- Assistant messages: left-aligned, neutral background
- Render markdown in assistant messages (use a simple regex-based approach:
  bold, italic, code blocks, inline code, links, lists)
- Show model name below assistant messages in small text

**MessageInput.tsx**:
- Textarea (auto-expanding, max 6 rows)
- Send button (disabled while streaming)
- Submit on Enter (Shift+Enter for newline)
- Disabled state during streaming with "Stop" button option

**ModelSelector.tsx**:
- Dropdown in the chat header area
- Shows current model for this conversation
- Fetches available models from settings endpoint
- Changing model updates the conversation

**SettingsPanel.tsx**:
- Accessed via gear icon in sidebar
- OpenRouter API key input (password field, saved to backend config)
- Default model selector
- System prompts: list, edit, create, delete
- Simple form-based editing, nothing fancy

### Styling Guidelines

- Dark background by default (gray-900 / gray-800)
- Light text (gray-100)
- Accent color for user messages and interactive elements (blue-600)
- Monospace font for code blocks
- Responsive breakpoint at 768px for mobile/desktop switch
- No animations except subtle transitions on sidebar

### Frontend Dockerfile

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
```

### frontend/nginx.conf

```nginx
server {
    listen 3000;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding off;
    }
}
```

---

## DOCKER COMPOSE

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    container_name: nexus-backend
    env_file: .env
    volumes:
      - ./backend/data:/app/data
    ports:
      - "8000:8000"
    restart: unless-stopped

  frontend:
    build: ./frontend
    container_name: nexus-frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
    restart: unless-stopped
```

### .env.example

```env
OPENROUTER_API_KEY=sk-or-v1-your-key-here
DEFAULT_MODEL=anthropic/claude-sonnet-4-20250514
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]
```

### .gitignore

```
__pycache__/
*.pyc
.env
backend/data/*.db
node_modules/
frontend/dist/
.DS_Store
*.log
```

---

## BUILD ORDER FOR AI AGENT

Execute these tasks in order. Each task should be completable in one
focused session. Test each task before moving to the next.

### Task 1: Project Scaffold
Create all directories and files listed in FILE STRUCTURE.
Create docker-compose.yml, .env.example, .gitignore, README.md.
Create both Dockerfiles and nginx.conf.
Create requirements.txt and package.json with all dependencies.
Verify: `docker compose build` succeeds for both containers.

### Task 2: Backend Core
Implement config.py, database.py (schema + seed), models.py.
Implement main.py with lifespan, CORS, health check.
Implement conversations router (full CRUD).
Implement settings router (config + system prompts).
Verify: `docker compose up backend` starts, `GET /api/health` returns 200,
conversation CRUD works via curl.

### Task 3: AI Streaming
Implement services/ai.py (OpenRouter client with streaming).
Implement services/prompts.py (message assembly).
Implement messages router (POST with SSE streaming).
Implement auto-title generation on first message.
Verify: `curl -N -X POST .../messages -d '{"content":"hello"}'`
returns streaming SSE events with AI response.

### Task 4: Frontend Shell
Initialize Vite + React + TypeScript + Tailwind.
Implement types/index.ts.
Implement api/client.ts.
Implement App.tsx layout (sidebar + main area).
Implement Sidebar.tsx (conversation list, new chat button).
Verify: frontend builds, shows sidebar with empty state.

### Task 5: Chat Interface
Implement useChat.ts hook.
Implement useStream.ts hook.
Implement ChatView.tsx, MessageList.tsx, MessageBubble.tsx, MessageInput.tsx.
Wire up: creating conversation, sending message, streaming response.
Verify: can send a message and see streamed AI response in browser.

### Task 6: Polish and Settings
Implement ModelSelector.tsx.
Implement SettingsPanel.tsx.
Add markdown rendering to MessageBubble.
Add mobile-responsive sidebar (hamburger menu).
Auto-scroll behavior during streaming.
Verify: full flow works on desktop and mobile viewport.

### Task 7: Docker Deployment
Verify docker compose up starts both services.
Verify frontend proxies API calls to backend via nginx.
Verify accessible from another device on same network via server IP:3000.
Write README.md with setup instructions.
Verify: phone browser can chat with assistant.

---

## ACCEPTANCE TESTS

These are the "done" criteria. Every item must pass.

### Functional
- [ ] Can create a new conversation
- [ ] Can send a message and receive a streamed AI response
- [ ] Response tokens appear in real-time (not all at once)
- [ ] Conversation history persists after page refresh
- [ ] Can switch between conversations
- [ ] Can delete a conversation
- [ ] Conversation auto-titles after first exchange
- [ ] Can change model per conversation
- [ ] Can edit system prompts
- [ ] Settings (API key, default model) persist

### Mobile
- [ ] Sidebar collapses on screens < 768px
- [ ] Chat is usable on phone-sized viewport
- [ ] Text input works on mobile keyboard
- [ ] Can create and use conversations from phone

### Deployment
- [ ] `docker compose up` starts everything
- [ ] Accessible at http://[server-ip]:3000 from another device
- [ ] Data survives container restart (SQLite on volume mount)
- [ ] Containers auto-restart on server reboot (restart: unless-stopped)

### Error Handling
- [ ] Invalid API key shows user-friendly error
- [ ] Network interruption during stream shows error, doesn't crash
- [ ] Empty message cannot be sent
- [ ] Missing API key on startup shows clear error in logs

---

## AGENT INSTRUCTIONS

If you are an AI agent building this project:

1. Follow the BUILD ORDER sequentially. Do not skip ahead.
2. After each task, verify it works before proceeding.
3. Do not add features, libraries, or files not in this spec.
4. Do not use an ORM. Use raw SQL with aiosqlite.
5. Do not add authentication. This is a private single-user tool.
6. Do not add WebSocket support. Use SSE via fetch + ReadableStream.
7. If something in this spec is ambiguous, choose the simpler option.
8. If a dependency version causes issues, use the latest stable.
9. Keep error handling simple: try/catch, log, return error response.
10. Commit after each completed task with message: "Task N: [description]"
