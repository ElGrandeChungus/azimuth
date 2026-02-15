# BUILD SPEC: Azimuth Phase 1 — Lore Map

> **Target agent**: AI IDE (Antigravity primary, portable to others)
> **Depends on**: Azimuth Shell (Phase 0) running and functional
> **Target platform**: Windows home server, Docker Desktop
> **Model provider**: OpenRouter

---

## OVERVIEW

Phase 1 adds the first "Map" (tool) to Azimuth: **Lore Map**, a
worldbuilding assistant that helps create, store, query, and
cross-reference canonical lore entries for the Taito System
Lancer campaign.

This phase adds three components:

1. **Lore Database** — SQLite database storing structured lore entries
   (NPCs, locations, factions, events, cultures) with schemas, cross-references,
   and full-text search.

2. **Lore MCP Server** — A Model Context Protocol server exposing lore
   tools that the Azimuth backend can call during conversations.

3. **Orchestration Pipeline** — Dual-model architecture where a cheap
   "producer" model handles background tasks (schema extraction, context
   retrieval, similarity ranking) and the conversation model handles
   creative content.

The interaction pattern: user describes lore naturally in conversation →
Azimuth identifies what's being created → retrieves relevant context →
asks smart follow-up questions → presents a structured entry for review →
stores it on approval.

---

## TECH STACK ADDITIONS

| Layer | Technology | Notes |
|-------|-----------|-------|
| MCP Server | FastMCP (Python) | `pip install fastmcp` — Pythonic MCP wrapper |
| Lore Database | SQLite via aiosqlite | Separate DB from Azimuth shell |
| Producer Model | OpenRouter (cheap model) | Gemini Flash, Haiku, or similar |
| Search | SQLite FTS5 | Full-text search, built into SQLite |

**Important**: The MCP server runs as a separate process from the Azimuth
backend. They communicate via the MCP protocol (Streamable HTTP transport).
If the MCP server crashes, the Azimuth shell still works — you just lose
lore tools until it restarts.

---

## ARCHITECTURE

```
┌──────────────────────────────────────────────────────────┐
│                     User (Browser)                        │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│                  Azimuth Backend                          │
│                  (FastAPI — existing)                      │
│                                                           │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ Conversation │  │ Orchestrator │  │  MCP Client    │  │
│  │   Router     │──│  (new)       │──│  (new)         │  │
│  │  (existing)  │  │              │  │                │  │
│  └─────────────┘  └──────┬───────┘  └───────┬────────┘  │
│                          │                    │           │
│                    ┌─────▼──────┐             │           │
│                    │ Producer   │             │           │
│                    │ Model Call │             │           │
│                    │ (cheap)    │             │           │
│                    └────────────┘             │           │
└──────────────────────────────────────────────┼───────────┘
                                               │ MCP Protocol
                                               │ (HTTP)
                                               ▼
┌──────────────────────────────────────────────────────────┐
│                  Lore Map MCP Server                      │
│                  (FastMCP — new container)                 │
│                                                           │
│  Tools:                        Database:                  │
│  ├─ create_entry              ┌──────────────┐           │
│  ├─ get_entry                 │  lore.db     │           │
│  ├─ search_entries            │  (SQLite)    │           │
│  ├─ list_entries              └──────────────┘           │
│  ├─ update_entry                                         │
│  ├─ delete_entry                                         │
│  ├─ get_schema                                           │
│  ├─ find_related                                         │
│  ├─ validate_references                                  │
│  └─ get_context_package                                  │
│                                                           │
│  Resources:                                               │
│  ├─ lore://schemas/{type}     Entry type schemas          │
│  ├─ lore://entries/{slug}     Individual entries           │
│  └─ lore://index/{type}       Entry listings by type      │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

---

## LORE DATABASE SCHEMA

Separate SQLite file: `loremap/data/lore.db`

```sql
-- Core entries table
CREATE TABLE IF NOT EXISTS entries (
    id TEXT PRIMARY KEY,                  -- UUID
    slug TEXT UNIQUE NOT NULL,            -- e.g., "seicoe-station"
    type TEXT NOT NULL CHECK(type IN (
        'location', 'faction', 'npc', 'event', 'culture'
    )),
    name TEXT NOT NULL,                   -- Display name
    category TEXT NOT NULL,               -- Type-specific subcategory
    status TEXT NOT NULL,                 -- Type-specific status enum
    parent_slug TEXT,                     -- For hierarchical relationships
    summary TEXT,                         -- 1-2 sentence summary for context
    content TEXT NOT NULL,                -- Full markdown body content
    metadata TEXT NOT NULL DEFAULT '{}',  -- JSON: type-specific fields
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Cross-references between entries
CREATE TABLE IF NOT EXISTS references (
    id TEXT PRIMARY KEY,
    source_slug TEXT NOT NULL,            -- Entry that contains the reference
    target_slug TEXT NOT NULL,            -- Entry being referenced
    target_type TEXT NOT NULL,            -- Type prefix for the target
    relationship TEXT,                    -- Optional: "controls", "allied", etc.
    FOREIGN KEY (source_slug) REFERENCES entries(slug) ON DELETE CASCADE,
    UNIQUE(source_slug, target_slug)
);

-- Lexicon terms (lightweight, no full entry needed)
CREATE TABLE IF NOT EXISTS lexicon (
    id TEXT PRIMARY KEY,
    term TEXT UNIQUE NOT NULL,
    definition TEXT NOT NULL,             -- 15-30 words max
    see_also TEXT,                        -- Optional type:slug reference
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Campaign threads (campaign-specific relationships)
CREATE TABLE IF NOT EXISTS threads (
    id TEXT PRIMARY KEY,
    entity_a TEXT NOT NULL,               -- Display name or slug
    entity_b TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    description TEXT NOT NULL,
    relevant_entries TEXT DEFAULT '[]',    -- JSON array of type:slug
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Campaign state (spine equivalent)
CREATE TABLE IF NOT EXISTS campaign_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Full-text search index
CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
    slug, name, summary, content,
    content='entries',
    content_rowid='rowid'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
    INSERT INTO entries_fts(rowid, slug, name, summary, content)
    VALUES (new.rowid, new.slug, new.name, new.summary, new.content);
END;

CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, slug, name, summary, content)
    VALUES ('delete', old.rowid, old.slug, old.name, old.summary, old.content);
END;

CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, slug, name, summary, content)
    VALUES ('delete', old.rowid, old.slug, old.name, old.summary, old.content);
    INSERT INTO entries_fts(rowid, slug, name, summary, content)
    VALUES (new.rowid, new.slug, new.name, new.summary, new.content);
END;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_entries_type ON entries(type);
CREATE INDEX IF NOT EXISTS idx_entries_parent ON entries(parent_slug);
CREATE INDEX IF NOT EXISTS idx_refs_source ON references(source_slug);
CREATE INDEX IF NOT EXISTS idx_refs_target ON references(target_slug);
```

### Type-Specific Metadata JSON Schemas

The `metadata` column stores type-specific fields as JSON.
These mirror the frontmatter schemas from the original template system.

**Location metadata:**
```json
{
    "parent_body": "",
    "controlled_by": "",
    "orbital_period": "",
    "atmosphere": "",
    "population": ""
}
```

**Faction metadata:**
```json
{
    "allegiance": "",
    "leader_slug": "",
    "base_of_operations_slug": "",
    "strength": "",
    "resources": []
}
```

**NPC metadata:**
```json
{
    "faction_slug": "",
    "location_slug": "",
    "disposition": "",
    "role": "",
    "appearance": "",
    "secrets": []
}
```

**Event metadata:**
```json
{
    "date_in_universe": "",
    "location_slug": "",
    "key_actors": [],
    "consequences": []
}
```

**Culture metadata:**
```json
{
    "associated_faction_slug": "",
    "associated_location_slug": "",
    "values": [],
    "practices": []
}
```

### Category and Status Enums

```python
ENTRY_SCHEMAS = {
    "location": {
        "categories": ["planet", "moon", "station", "settlement", "region"],
        "statuses": ["active", "abandoned", "contested", "restricted"],
    },
    "faction": {
        "categories": ["corporation", "clan", "government", "insurgency",
                       "religious", "military", "other"],
        "statuses": ["active", "dissolved", "underground", "rising", "declining"],
    },
    "npc": {
        "categories": ["leader", "diplomat", "soldier", "civilian",
                       "criminal", "scholar", "other"],
        "statuses": ["alive", "dead", "missing", "unknown"],
    },
    "event": {
        "categories": ["battle", "political", "disaster", "discovery",
                       "cultural", "personal"],
        "statuses": ["historical", "ongoing", "imminent", "secret"],
    },
    "culture": {
        "categories": ["ethnic", "regional", "religious", "professional", "other"],
        "statuses": ["active", "declining", "extinct", "evolving"],
    },
}
```

---

## FILE STRUCTURE

New files and directories to add to the Azimuth project:

```
azimuth/
├── (existing Phase 0 files)
│
├── loremap/                            # NEW — Lore Map MCP server
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── __init__.py
│   │   ├── server.py                   # FastMCP server definition + tools
│   │   ├── database.py                 # SQLite init, connection, queries
│   │   ├── schemas.py                  # Entry type schemas and validation
│   │   ├── models.py                   # Pydantic models for entries
│   │   └── search.py                   # FTS5 search + similarity helpers
│   └── data/
│       └── .gitkeep                    # lore.db created at runtime
│
├── backend/
│   ├── (existing files)
│   └── app/
│       ├── (existing files)
│       ├── services/
│       │   ├── (existing files)
│       │   ├── mcp_client.py           # NEW — MCP client for calling Lore Map
│       │   ├── orchestrator.py         # NEW — Dual-model pipeline coordinator
│       │   └── producer.py             # NEW — Cheap model for background tasks
│       └── routers/
│           ├── (existing files)
│           └── lore.py                 # NEW — REST endpoints for lore UI
│
└── docker-compose.yml                  # MODIFIED — add loremap service
```

---

## MCP SERVER SPECIFICATION

### loremap/app/server.py

The MCP server using FastMCP. Exposes tools and resources.

```python
from fastmcp import FastMCP

mcp = FastMCP(
    "Lore Map",
    description="Worldbuilding lore management for the Taito System"
)
```

### MCP Tools

Each tool is a function decorated with `@mcp.tool()`.

#### create_entry

```
Input: {
    type: str,          # "location" | "faction" | "npc" | "event" | "culture"
    name: str,          # Display name
    category: str,      # Type-specific subcategory
    status: str,        # Type-specific status
    summary: str,       # 1-2 sentence summary
    content: str,       # Full markdown body
    metadata: dict,     # Type-specific fields (see schemas above)
    references: list,   # Array of {target_slug, target_type, relationship}
    parent_slug: str    # Optional parent entry slug
}
Output: { entry: full_entry_object, warnings: list }
```

Behavior:
1. Generate slug from name (lowercase, hyphen-separated)
2. Validate type, category, status against schema enums
3. Validate all reference target_slugs exist (warn if not, don't block)
4. Insert into entries table
5. Insert reference rows
6. Return created entry with any validation warnings

#### get_entry

```
Input: { slug: str }
Output: { entry: full_entry_object, references: list, referenced_by: list }
```

Returns the entry plus bidirectional cross-references.

#### search_entries

```
Input: { query: str, type: str (optional), limit: int (default 10) }
Output: { results: list_of_entries_with_relevance_scores }
```

Uses FTS5 for full-text search. Optional type filter.

#### list_entries

```
Input: { type: str (optional), parent_slug: str (optional) }
Output: { entries: list_of_summary_objects }
```

Returns compact list (slug, name, type, category, status, summary).
No full content — for index/overview purposes.

#### update_entry

```
Input: { slug: str, updates: dict }
Output: { entry: updated_entry_object }
```

Partial update. Only provided fields are changed.
Updates `updated_at` timestamp.

#### delete_entry

```
Input: { slug: str }
Output: { deleted: bool, orphaned_references: list }
```

Deletes entry and its outbound references.
Returns list of other entries that referenced this one (now orphaned).

#### get_schema

```
Input: { type: str }
Output: { schema: full_schema_definition }
```

Returns the complete schema for a given entry type: required fields,
optional fields, category enums, status enums, metadata shape,
and content section templates.

#### find_related

```
Input: { slug: str, limit: int (default 5) }
Output: { related: list_of_entries_with_similarity_scores }
```

Finds entries related to the given entry by:
1. Direct references (highest relevance)
2. Shared parent_slug (same region/system)
3. Shared references (entries that reference the same things)
4. FTS5 similarity (content overlap)

#### validate_references

```
Input: { slug: str (optional — validates all if omitted) }
Output: { valid: list, broken: list, orphaned: list }
```

Checks all cross-references for integrity.
- Valid: both source and target exist
- Broken: target doesn't exist
- Orphaned: entry exists but nothing references it

#### get_context_package

```
Input: {
    entry_type: str,           # What type of entry is being created
    user_input: str,           # Raw user message text
    existing_slug: str         # Optional: if modifying existing entry
}
Output: {
    schema: dict,              # Relevant entry schema
    filled_fields: dict,       # Fields extractable from user input
    missing_required: list,    # Required fields still needed
    related_entries: list,     # Relevant existing entries for context
    suggested_references: list,# Potential cross-references
    follow_up_questions: list  # Questions to ask the user
}
```

This is the key tool the orchestrator calls. It packages everything
the conversation model needs to have a smart worldbuilding discussion.

### MCP Resources

```python
@mcp.resource("lore://schemas/{type}")
# Returns the full schema definition for the given entry type

@mcp.resource("lore://entries/{slug}")
# Returns a single entry in full detail

@mcp.resource("lore://index/{type}")
# Returns a compact listing of all entries of a given type
```

---

## ORCHESTRATION PIPELINE

### How a message flows through the system

```
User sends message: "I want to add an NPC who lives in the Drift"
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│ Step 1: DETECT INTENT (orchestrator.py)                  │
│                                                          │
│ Orchestrator checks if the message involves lore:        │
│ - Contains lore-related keywords?                        │
│ - References known entry types?                          │
│ - Mentions known locations/factions/NPCs?                │
│                                                          │
│ If no lore intent → normal chat (skip pipeline)          │
│ If lore intent → continue to Step 2                      │
│                                                          │
│ Method: Producer model call with classification prompt   │
└────────────────────────────┬────────────────────────────┘
                              │ lore intent detected
                              ▼
┌─────────────────────────────────────────────────────────┐
│ Step 2: EXTRACT + RETRIEVE (producer.py + MCP tools)     │
│                                                          │
│ a) Producer model extracts structured info:              │
│    - Entry type (npc)                                    │
│    - Fields mentioned (location: "the Drift")            │
│    - Known terms that need context lookup                │
│                                                          │
│ b) MCP tool calls:                                       │
│    - get_schema("npc") → NPC schema                     │
│    - search_entries("Drift") → matching locations        │
│    - list_entries(type="npc", parent_slug="taito-system")│
│      → existing NPCs in the same system                 │
│    - get_context_package(type="npc", input=msg)          │
│      → assembled context bundle                         │
│                                                          │
│ Producer model is cheap (Gemini Flash, Haiku, etc.)      │
└────────────────────────────┬────────────────────────────┘
                              │ context package assembled
                              ▼
┌─────────────────────────────────────────────────────────┐
│ Step 3: COMPOSE RESPONSE (conversation model)            │
│                                                          │
│ The conversation model (Sonnet, etc.) receives:          │
│ - The user's original message                            │
│ - The context package from Step 2                        │
│ - System prompt with worldbuilding instructions          │
│ - Conversation history                                   │
│                                                          │
│ It generates a natural response:                         │
│ - Acknowledges what the user said                        │
│ - Asks follow-up questions based on missing fields       │
│ - Uses retrieved context to ask informed questions       │
│ - References related entries naturally                   │
│                                                          │
│ This is the response the user sees.                      │
└────────────────────────────┬────────────────────────────┘
                              │
                              ▼
            (User responds with more details)
                              │
                              ▼
        (Steps 1-3 repeat until entry is complete)
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│ Step 4: PRESENT FOR REVIEW                               │
│                                                          │
│ When enough fields are filled, the conversation model    │
│ presents the assembled entry in a readable format.       │
│ Shows: filled schema, related entries, suggested         │
│ cross-references.                                        │
│                                                          │
│ User reviews and approves / requests changes.            │
└────────────────────────────┬────────────────────────────┘
                              │ user approves
                              ▼
┌─────────────────────────────────────────────────────────┐
│ Step 5: COMMIT (MCP tools)                               │
│                                                          │
│ Orchestrator calls:                                      │
│ - create_entry() with full entry data                    │
│ - Cross-references auto-created                          │
│ - validate_references() to check integrity               │
│                                                          │
│ Confirmation shown to user.                              │
└─────────────────────────────────────────────────────────┘
```

### backend/app/services/orchestrator.py

The orchestrator sits between the message router and the AI service.
It intercepts messages, runs the producer pipeline if lore-related,
and augments the conversation model's context.

```python
class Orchestrator:
    """Coordinates the dual-model pipeline for lore-aware conversations."""

    async def process_message(self, message, conversation, history):
        """
        Main entry point. Called by messages router before AI response.

        Returns an augmented system prompt and/or injected context
        that the conversation model uses to generate its response.
        """

        # Step 1: Detect lore intent
        intent = await self.detect_intent(message, history)

        if not intent.is_lore_related:
            return None  # Normal chat, no augmentation

        # Step 2: Build context package
        context = await self.build_context(intent, message, history)

        # Step 3: Return augmented prompt for conversation model
        return self.compose_augmented_prompt(context)

    async def detect_intent(self, message, history):
        """Use producer model to classify message intent."""
        # Calls producer.py with a classification prompt
        pass

    async def build_context(self, intent, message, history):
        """Call MCP tools to retrieve relevant lore context."""
        # Calls MCP client to invoke get_context_package, search, etc.
        pass

    async def compose_augmented_prompt(self, context):
        """Build the context injection for the conversation model."""
        # Formats context package into a structured prompt section
        pass
```

### backend/app/services/producer.py

Wrapper for cheap model calls used in the orchestration pipeline.

```python
class Producer:
    """Cheap model for background classification and extraction."""

    def __init__(self, model="google/gemini-flash-2.0"):
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.OPENROUTER_API_KEY,
        )
        self.model = model

    async def classify_intent(self, message, history_summary):
        """Determine if message involves lore creation/query/update."""
        # Returns: {is_lore: bool, intent_type: str, entry_type: str}
        pass

    async def extract_fields(self, message, schema):
        """Pull structured fields from natural language input."""
        # Returns: dict of field_name: extracted_value
        pass

    async def generate_follow_ups(self, schema, filled, missing):
        """Generate natural follow-up questions for missing fields."""
        # Returns: list of question strings
        pass
```

### backend/app/services/mcp_client.py

Client that connects to the Lore Map MCP server.

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

class LoreMapClient:
    """MCP client for calling Lore Map server tools."""

    def __init__(self, server_url="http://loremap:8001/mcp"):
        self.server_url = server_url

    async def call_tool(self, tool_name, arguments):
        """Call an MCP tool and return the result."""
        async with streamablehttp_client(self.server_url) as (r, w, _):
            async with ClientSession(r, w) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                return result

    # Convenience methods
    async def create_entry(self, **kwargs):
        return await self.call_tool("create_entry", kwargs)

    async def get_entry(self, slug):
        return await self.call_tool("get_entry", {"slug": slug})

    async def search(self, query, type=None, limit=10):
        return await self.call_tool("search_entries",
            {"query": query, "type": type, "limit": limit})

    async def get_context_package(self, entry_type, user_input):
        return await self.call_tool("get_context_package",
            {"entry_type": entry_type, "user_input": user_input})

    async def find_related(self, slug, limit=5):
        return await self.call_tool("find_related",
            {"slug": slug, "limit": limit})
```

---

## BACKEND MODIFICATIONS

### Modified: backend/app/routers/messages.py

The existing message endpoint gains orchestration:

```python
# BEFORE (Phase 0):
# 1. Save user message
# 2. Load history
# 3. Load system prompt
# 4. Call AI model
# 5. Stream response

# AFTER (Phase 1):
# 1. Save user message
# 2. Load history
# 3. Load system prompt
# 4. >>> Run orchestrator.process_message() <<<
# 5. >>> If lore context returned, inject into messages array <<<
# 6. Call AI model (with augmented context)
# 7. Stream response
# 8. >>> If response contains approval trigger, call MCP to save <<<
```

The key change: between loading history and calling the AI model,
the orchestrator runs. If it detects lore intent, it injects a
context block into the messages array as a system message, giving
the conversation model everything it needs.

### New: backend/app/routers/lore.py

REST endpoints for direct lore operations from the frontend
(browsing entries, manual edits outside of conversation).

```
GET    /api/lore/entries              List entries (filterable by type)
GET    /api/lore/entries/:slug        Get single entry with references
POST   /api/lore/entries              Create entry directly (bypass conversation)
PATCH  /api/lore/entries/:slug        Update entry
DELETE /api/lore/entries/:slug        Delete entry
GET    /api/lore/search?q=            Full-text search
GET    /api/lore/schemas/:type        Get schema for entry type
GET    /api/lore/health               Check MCP server connectivity
```

These proxy through the MCP client — the backend doesn't access
the lore database directly. All lore operations go through MCP.

---

## DOCKER COMPOSE ADDITIONS

Add to existing `docker-compose.yml`:

```yaml
  loremap:
    build: ./loremap
    container_name: azimuth-loremap
    volumes:
      - ./loremap/data:/app/data
    ports:
      - "127.0.0.1:8001:8001"    # Only accessible from server itself
    restart: unless-stopped
    environment:
      - DATABASE_PATH=data/lore.db
```

Update backend service to depend on loremap:

```yaml
  backend:
    # ... existing config ...
    depends_on:
      - loremap
    environment:
      # ... existing env ...
      - LOREMAP_MCP_URL=http://loremap:8001/mcp
      - PRODUCER_MODEL=google/gemini-flash-2.0
```

### loremap/Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/
COPY data/ data/
EXPOSE 8001
CMD ["python", "-m", "app.server"]
```

### loremap/requirements.txt

```
fastmcp>=3.0.0
aiosqlite==0.20.0
pydantic==2.10.3
uvicorn[standard]==0.34.0
```

---

## SYSTEM PROMPT ADDITIONS

When lore tools are active, append this to the conversation's
system prompt:

```
## Worldbuilding Mode

You have access to a worldbuilding lore database for the Taito System
(a Lancer RPG setting). When the user discusses worldbuilding:

- Check the context package provided for existing lore and schemas
- Ask follow-up questions based on missing required fields
- Reference related entries naturally in conversation
- When enough information is gathered, present the entry for review
- Only save entries when the user explicitly approves

Entry types: location, faction, npc, event, culture
Each has specific required fields — check the schema before asking questions.

When presenting an entry for review, format it clearly with all fields
shown. Mark any fields you filled in vs. fields the user explicitly stated.

Do not invent lore. Only record what the user confirms as canon.
```

---

## FRONTEND ADDITIONS (Minimal for Phase 1)

Phase 1 frontend changes are minimal. The main interaction is
still through conversation. Add only:

### Lore Browser Panel

A simple panel (accessible from sidebar or settings) that shows:
- List of all lore entries grouped by type
- Click to view entry details
- Search box for full-text search
- Basic stats (entry count by type)

This is a read-only viewer for now. All creation/editing happens
through conversation. Direct editing can be added later.

### Entry Review Component

When the AI presents an entry for review during conversation,
render it in a structured card format rather than raw markdown.
Show: name, type, category, status, summary, filled fields,
suggested references, and approve/edit/reject buttons.

---

## BUILD ORDER

### Task 1: Lore Map MCP Server Scaffold
Create `loremap/` directory structure and all files.
Implement `database.py` with schema creation and seeding.
Implement `schemas.py` with entry type definitions and validation.
Implement `models.py` with Pydantic models.
Create Dockerfile and requirements.txt.
**Verify:** Container builds and starts. Database file created.

### Task 2: MCP Tools — CRUD
Implement `server.py` with FastMCP setup.
Implement tools: create_entry, get_entry, update_entry,
delete_entry, list_entries, get_schema.
**Verify:** Can create, read, update, delete entries via MCP
inspector or test script. Schema validation works.

### Task 3: MCP Tools — Search and Relations
Implement `search.py` with FTS5 search logic.
Implement tools: search_entries, find_related, validate_references.
**Verify:** Full-text search returns ranked results. find_related
returns entries by reference proximity and content similarity.

### Task 4: MCP Context Package
Implement get_context_package tool — the key orchestration tool.
This assembles schema, filled fields, missing fields, related
entries, and suggested references into a single response.
**Verify:** Given entry type + user input, returns a complete
context package with correctly identified fields and context.

### Task 5: Backend — MCP Client + Producer
Add `mcp_client.py` to backend services.
Add `producer.py` with cheap model classification and extraction.
Add `orchestrator.py` coordinating the pipeline.
Update docker-compose.yml with loremap service and dependencies.
**Verify:** Backend can connect to MCP server and call tools.
Producer model can classify messages and extract fields.

### Task 6: Backend — Message Pipeline Integration
Modify `messages.py` router to call orchestrator before AI response.
Add context injection into conversation model's message array.
Add lore.py router with REST proxy endpoints.
**Verify:** Sending a lore-related message triggers the pipeline.
Context package appears in the conversation model's input.
Conversation model asks informed follow-up questions.

### Task 7: Frontend — Lore Browser
Add lore browser panel to the frontend.
Add entry review card component for in-conversation display.
Wire up lore REST endpoints.
**Verify:** Can browse entries by type, search, view details.
Entry review card renders during lore conversations.

### Task 8: Integration Testing
Test full flow: describe an NPC → follow-ups → review → approve → saved.
Test search and retrieval of saved entries.
Test cross-reference integrity across multiple entries.
Test that non-lore conversations work normally (no pipeline interference).
**Verify:** All acceptance tests pass.

---

## ACCEPTANCE TESTS

### MCP Server
- [ ] Can create entries of all 5 types with valid schemas
- [ ] Schema validation rejects invalid category/status values
- [ ] Cross-references are created bidirectionally
- [ ] Full-text search returns relevant results ranked by relevance
- [ ] find_related returns entries by reference proximity
- [ ] validate_references correctly identifies broken references
- [ ] get_context_package returns complete context for any entry type
- [ ] MCP server starts independently and survives backend restart

### Orchestration Pipeline
- [ ] Non-lore messages pass through without pipeline activation
- [ ] Lore-related messages trigger context retrieval
- [ ] Producer model correctly classifies message intent
- [ ] Producer model extracts structured fields from natural language
- [ ] Context package is injected into conversation model's input
- [ ] Conversation model asks informed follow-up questions
- [ ] Multiple conversation turns accumulate entry data correctly

### End-to-End
- [ ] Can create an NPC through natural conversation
- [ ] Can create a location through natural conversation
- [ ] Entry presented for review shows all fields clearly
- [ ] Approved entry is saved to database with correct schema
- [ ] Cross-references to existing entries are created automatically
- [ ] Saved entry appears in lore browser
- [ ] Saved entry is findable via search
- [ ] Editing an existing entry through conversation works
- [ ] Querying lore ("tell me about Seicoe Station") retrieves entry

### Resilience
- [ ] Azimuth chat works normally when MCP server is down
- [ ] MCP server restart doesn't lose data (SQLite on volume)
- [ ] Multiple rapid lore operations don't cause race conditions
- [ ] Large entries (2000+ words) are handled without issues

---

## AGENT INSTRUCTIONS

If you are an AI agent building this:

1. Follow BUILD ORDER sequentially. Each task builds on the previous.
2. The Lore Map MCP server is a SEPARATE container. Do not merge it
   into the Azimuth backend.
3. Use FastMCP (pip install fastmcp) for the MCP server. Do not
   write raw MCP protocol handling.
4. Use the openai SDK for producer model calls (same pattern as
   the existing AI service).
5. Do not modify existing Phase 0 functionality. Chat without lore
   must continue working exactly as before.
6. All lore database access goes through MCP tools. The backend
   never imports from loremap directly.
7. The producer model defaults to google/gemini-flash-2.0 but
   should be configurable via environment variable.
8. Keep the frontend additions minimal. The primary interface is
   conversation, not a CRUD form.
9. If something in this spec is ambiguous, choose the simpler option.
10. Commit after each completed task.

---
