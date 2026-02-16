# BUILD SPEC: Foundry Forge — Lore Map to Foundry VTT Formatter

> **Depends on**: Azimuth Phase 1 (Lore Map MCP server operational)
> **Target platform**: Windows home server, Docker Desktop
> **Foundry version**: v12.343, Lancer system v2.11.1
> **Module dependency**: Monk's Enhanced Journal (MEJ)

---

## OVERVIEW

Foundry Forge adds export capabilities to the Lore Map MCP server,
enabling Azimuth to produce Foundry VTT-importable JSON from canonical
lore entries. This is a rendering pipeline, not a live bridge — the
Lore Map remains the source of truth, and Foundry JSON is an output
format like any other.

The system has two parts:

1. **Schema Reference** — Documentation that teaches Azimuth how
   Foundry v12 + Lancer + Monk's Enhanced Journal structures its
   data, stored as a lore entry or system prompt appendix.

2. **Formatter Tools** — MCP tools on the Lore Map server that
   accept a lore entry slug and produce valid, importable Foundry
   JSON documents.

The interaction pattern: user creates/refines lore in conversation →
requests Foundry export → formatter reads lore entry + resolves
cross-references → produces JSON → user imports into Foundry via
its built-in import UI or drops into world data folder.

---

## FOUNDRY v12 JOURNAL ENTRY SCHEMA ANALYSIS

Based on real exports from a Lancer world running Foundry v12.343,
Lancer system v2.11.1, with Monk's Enhanced Journal.

### Document Envelope

Every Foundry JournalEntry export follows this outer structure:

```json
{
  "name": "<display name>",
  "flags": {
    "monks-enhanced-journal": {
      "pagetype": "<person|place|quest|shop|loot|poi|organization>",
      "img": "<relative path to header image>"
    },
    "exportSource": {
      "world": "<world id>",
      "system": "lancer",
      "coreVersion": "12.343",
      "systemVersion": "2.11.1"
    }
  },
  "pages": [ <page objects> ],
  "folder": null,
  "_stats": {
    "coreVersion": "12.343",
    "systemId": "lancer",
    "systemVersion": "2.11.1",
    "createdTime": <unix ms>,
    "modifiedTime": <unix ms>,
    "lastModifiedBy": "<user id>"
  }
}
```

Key observations:
- `flags.monks-enhanced-journal.pagetype` controls how MEJ renders
  the entry. This is the critical type discriminator.
- `flags.exportSource` records provenance. When generating, use a
  distinct world name like "azimuth-export" to track generated content.
- `folder` is null for standalone entries. Foundry can auto-sort on
  import, or the user can organize manually.
- `_stats.lastModifiedBy` references a Foundry user ID. Generated
  exports should use a placeholder ID or omit this field (Foundry
  reassigns on import).
- Timestamps are Unix milliseconds, not ISO strings.

### Page Object (MEJ Person Type)

Used for NPC entries. Single page per journal entry.

```json
{
  "type": "text",
  "name": "<character name>",
  "flags": {
    "monks-enhanced-journal": {
      "type": "person",
      "role": "<role string, e.g. 'NPC - Fixer'>",
      "location": "<location display name>",
      "attributes": {
        "ancestry": "<species/ancestry>",
        "age": "<age string>",
        "eyes": "<eye color>",
        "hair": "<hair description>",
        "voice": "<voice quality>",
        "traits": "<personality trait summary>",
        "ideals": "<core belief or ideal>",
        "bonds": "<what they care about>",
        "flaws": "<weakness or limitation>"
      },
      "relationships": [
        {
          "id": "<target journal entry Foundry ID>",
          "uuid": "JournalEntry.<target Foundry ID>",
          "hidden": false,
          "name": "<target display name>",
          "img": "<target image path>",
          "type": "<person|place>",
          "relationship": "<relationship description>"
        }
      ]
    }
  },
  "_id": "<page ID, alphanumeric 16-char>",
  "system": {},
  "title": { "show": true, "level": 1 },
  "image": {},
  "text": {
    "format": 1,
    "content": "<HTML body content>"
  },
  "video": { "controls": true, "volume": 0.5 },
  "src": "<image path, same as header>",
  "sort": 0,
  "ownership": {
    "default": -1
  },
  "_stats": {
    "compendiumSource": null,
    "duplicateSource": null,
    "coreVersion": "12.343",
    "systemId": "lancer",
    "systemVersion": "2.11.1",
    "createdTime": <unix ms>,
    "modifiedTime": <unix ms>,
    "lastModifiedBy": "<user id>"
  }
}
```

Key observations:
- `attributes` maps loosely to D&D-style attribute blocks but the
  keys are freeform strings. MEJ renders whatever keys are present.
- `relationships` array links to other JournalEntry documents by
  their Foundry document ID. Generated exports cannot know these IDs
  in advance — they must use placeholder IDs that get resolved on
  import, or use a two-pass export (export all, then patch IDs).
- `text.content` is HTML (format: 1). Markdown must be converted.
- `text.format`: 1 = HTML, 2 = Markdown. Foundry v12 uses HTML
  internally even when displaying markdown.
- `ownership.default: -1` means no default permission. The GM
  user ID gets level 3 (owner). Generated exports should set
  `"default": -1` and let the GM assign permissions on import.
- `src` is the portrait/header image path. Optional for generated
  entries — can be left as empty string and filled in Foundry.

### Page Object (MEJ Place Type)

Used for location entries.

```json
{
  "flags": {
    "monks-enhanced-journal": {
      "type": "place",
      "placetype": "<place classification string>",
      "location": "<parent location / region string>",
      "attributes": {
        "age": "<founding date or age>",
        "size": "<size classification>",
        "government": "<governance type>",
        "inhabitants": "<population description, can be multi-line>"
      },
      "relationships": [ <same structure as person type> ]
    }
  }
}
```

Key observations:
- `placetype` is a freeform string, not an enum. Examples from
  exports: "Artificial Orbital Habitat", "Planet (Former Colony Site)".
  The formatter should produce descriptive strings, not slugs.
- `attributes.inhabitants` can contain multi-line text with full
  paragraphs. This is where detailed demographic/status info goes.
- `location` is the parent context string, e.g. "Taito System" or
  "Taito System, Orbiting Seicoe Prime".

---

## LORE MAP → FOUNDRY FIELD MAPPING

### NPC Entry → MEJ Person JournalEntry

| Lore Map Field | Foundry Field | Transform |
|----------------|---------------|-----------|
| `name` | `name`, `pages[0].name` | Direct copy |
| `slug` | (used for filename) | `fvtt-JournalEntry-{slug}.json` |
| `category` | `pages[0].flags.monks-enhanced-journal.role` | Prefix with "NPC - ", title case category |
| `metadata.location_slug` | `pages[0].flags.monks-enhanced-journal.location` | Resolve slug → entry name |
| `metadata.appearance` | `pages[0].flags.monks-enhanced-journal.attributes.traits` | Direct copy |
| `metadata.disposition` | `pages[0].flags.monks-enhanced-journal.attributes.ideals` | Map to character ideal |
| `metadata.secrets` | GM notes in `text.content` or attributes | Include in body under secrets header |
| `metadata.role` | `pages[0].flags.monks-enhanced-journal.role` | Combine with category |
| `content` | `pages[0].text.content` | Markdown → HTML conversion |
| `references` | `pages[0].flags.monks-enhanced-journal.relationships` | Resolve slugs → relationship objects |

**NPC attributes mapping strategy:**

The MEJ person `attributes` object has flexible keys. The formatter
should populate these keys to maximize MEJ's display:

```
ancestry    ← extract from content or default to "Human"
age         ← extract from content or leave empty
eyes        ← extract from appearance or leave empty
hair        ← extract from appearance or leave empty
voice       ← extract from content or leave empty
traits      ← metadata.appearance (physical/behavioral description)
ideals      ← extract from content (Personality & Motivation section)
bonds       ← extract from content (Relationships section, condensed)
flaws       ← extract from content (weaknesses, limitations)
```

These extractions are best handled by the conversation model at
export time rather than rigid field mapping — the model reads the
full lore entry content and populates the attributes intelligently.

### Location Entry → MEJ Place JournalEntry

| Lore Map Field | Foundry Field | Transform |
|----------------|---------------|-----------|
| `name` | `name`, `pages[0].name` | Direct copy |
| `slug` | (used for filename) | `fvtt-JournalEntry-{slug}.json` |
| `category` | `pages[0].flags.monks-enhanced-journal.placetype` | Descriptive string from category enum |
| `metadata.parent_body` | `pages[0].flags.monks-enhanced-journal.location` | Resolve to location context string |
| `metadata.controlled_by` | `pages[0].flags.monks-enhanced-journal.attributes.government` | Resolve slug → faction name + type |
| `metadata.population` | `pages[0].flags.monks-enhanced-journal.attributes.inhabitants` | Direct copy, can be multi-line |
| `metadata.atmosphere` | Include in body content | Part of physical description |
| `content` | `pages[0].text.content` | Markdown → HTML conversion |
| `references` | `pages[0].flags.monks-enhanced-journal.relationships` | Resolve slugs → relationship objects |

**Location placetype mapping:**

| Lore Map category | Foundry placetype string |
|-------------------|--------------------------|
| `planet` | "Planet" (append detail from content if available) |
| `moon` | "Moon" |
| `station` | "Orbital Station" or "Space Station" |
| `settlement` | "Settlement" or "Colony" |
| `region` | "Region" |

The formatter should enrich these with parenthetical detail from
content when available, e.g. "Planet (Former Colony Site)" rather
than bare "Planet".

### Faction Entry → MEJ Organization JournalEntry

MEJ supports an "organization" page type. Mapping:

| Lore Map Field | Foundry Field | Transform |
|----------------|---------------|-----------|
| `name` | `name`, `pages[0].name` | Direct copy |
| `category` | `attributes.type` or body | Organization type string |
| `metadata.allegiance` | `attributes` or body | Political alignment |
| `metadata.leader_slug` | `relationships[]` | Resolve to person relationship |
| `metadata.base_of_operations_slug` | `relationships[]` | Resolve to place relationship |
| `metadata.strength` | `attributes` or body | Force description |
| `content` | `pages[0].text.content` | Markdown → HTML |

### Event Entry → MEJ JournalEntry (text type)

Events don't have a dedicated MEJ page type. Export as standard
text journal entries with structured HTML body:

| Lore Map Field | Foundry Field | Transform |
|----------------|---------------|-----------|
| `name` | `name` | Direct copy |
| `metadata.date_in_universe` | Body header or attribute | Include as first line |
| `metadata.location_slug` | Body reference | Resolve to name |
| `metadata.key_actors` | Body list | Resolve slugs to names |
| `content` | `pages[0].text.content` | Markdown → HTML |

### Culture Entry → MEJ JournalEntry (text type)

Same approach as events — standard text journal with structured body.

---

## CROSS-REFERENCE RESOLUTION

The hardest part of the formatter. Foundry relationships reference
entries by their Foundry document ID (e.g., `"id": "0SQvO3BxP0Hs20tg"`),
which doesn't exist until the entry is imported into Foundry.

### Strategy: Placeholder IDs + Import Manifest

When exporting, the formatter:

1. Generates a deterministic placeholder ID for each entry based
   on its slug (e.g., SHA-256 hash of slug, truncated to 16 chars,
   using only alphanumeric characters to match Foundry's ID format).

2. Uses these placeholder IDs in all `relationships[].id` and
   `relationships[].uuid` fields across the export batch.

3. Produces an **import manifest** alongside the JSON files that
   maps slugs → placeholder IDs, so the user (or a future import
   macro) can batch-import and have internal cross-references
   resolve correctly.

4. If entries already exist in Foundry (known IDs from a previous
   export session), the formatter can accept an ID mapping override
   to use real Foundry IDs instead of placeholders.

### Placeholder ID Generation

```python
import hashlib

def slug_to_foundry_id(slug: str) -> str:
    """Generate a deterministic 16-char alphanumeric ID from a slug."""
    hash_bytes = hashlib.sha256(slug.encode()).hexdigest()
    # Foundry IDs are 16 chars, mixed case alphanumeric
    # Use first 16 hex chars (lowercase) as a safe subset
    return hash_bytes[:16]
```

This ensures that exporting the same entry twice produces the same
placeholder ID, so cross-references remain consistent across
export batches.

### Relationship Object Construction

```python
def build_relationship(
    target_slug: str,
    target_name: str,
    target_type: str,       # lore map type: "npc", "location", etc.
    relationship_desc: str,
    target_img: str = "",
    hidden: bool = False,
) -> dict:
    """Build a Foundry MEJ relationship object."""
    foundry_id = slug_to_foundry_id(target_slug)
    mej_type_map = {
        "npc": "person",
        "location": "place",
        "faction": "organization",
        "event": "person",     # no native MEJ type; fallback
        "culture": "person",   # no native MEJ type; fallback
    }
    return {
        "id": foundry_id,
        "uuid": f"JournalEntry.{foundry_id}",
        "hidden": hidden,
        "name": target_name,
        "img": target_img,
        "type": mej_type_map.get(target_type, "person"),
        "relationship": relationship_desc,
    }
```

---

## MCP TOOLS

Add these tools to the existing Lore Map MCP server (loremap service).
They extend the existing tool set — no new container required.

### export_to_foundry

```
Input: {
    slug: str,                    # Entry to export
    include_related: bool,        # If true, also export referenced entries
    id_overrides: dict (optional) # Map of slug → known Foundry ID
}
Output: {
    entries: [
        {
            slug: str,
            filename: str,        # e.g. "fvtt-JournalEntry-cintra-gables.json"
            json: str,            # Complete Foundry JSON as string
            type: str,            # Lore map entry type
            foundry_type: str     # MEJ page type used
        }
    ],
    manifest: {
        exported_at: str,         # ISO timestamp
        foundry_version: "12.343",
        system: "lancer",
        system_version: "2.11.1",
        id_map: dict              # slug → placeholder/override ID
    }
}
```

This is the primary export tool. When `include_related` is true, it
walks the entry's references and exports all connected entries in a
single batch with consistent cross-reference IDs.

### export_batch_to_foundry

```
Input: {
    slugs: list[str],            # Multiple entries to export
    id_overrides: dict (optional)
}
Output: same structure as export_to_foundry
```

For bulk exports — e.g., "export all NPCs for Mission 1."

### get_foundry_schema

```
Input: {
    entry_type: str              # "npc", "location", "faction", etc.
}
Output: {
    schema: dict,                # Annotated Foundry JSON template
    field_mapping: dict,         # Lore Map field → Foundry field
    notes: str                   # Human-readable mapping guidance
}
```

Reference tool — lets the conversation model understand the Foundry
schema when discussing exports with the user.

---

## IMPLEMENTATION

### New Files

```
loremap/
├── app/
│   ├── (existing files)
│   ├── foundry_formatter.py    # Core formatting logic
│   └── foundry_schemas.py      # Foundry JSON templates and constants
```

No new containers. No new dependencies. The formatter is pure Python
that produces JSON strings.

### foundry_schemas.py

Constants and templates for Foundry JSON generation:

```python
FOUNDRY_VERSION = "12.343"
LANCER_SYSTEM_ID = "lancer"
LANCER_SYSTEM_VERSION = "2.11.1"
EXPORT_WORLD_NAME = "azimuth-export"

# MEJ page type mapping from lore entry types
MEJ_PAGE_TYPES = {
    "npc": "person",
    "location": "place",
    "faction": "organization",
    "event": "text",
    "culture": "text",
}

# Foundry document envelope template
def journal_entry_envelope(
    name: str,
    page_type: str,
    header_img: str = "",
) -> dict:
    """Returns the outer JournalEntry structure."""
    ...

# Page templates for each MEJ type
def person_page(
    name: str,
    role: str,
    location: str,
    attributes: dict,
    html_content: str,
    relationships: list,
    image_src: str = "",
) -> dict:
    """Returns a complete MEJ person page object."""
    ...

def place_page(
    name: str,
    placetype: str,
    location: str,
    attributes: dict,
    html_content: str,
    relationships: list,
    image_src: str = "",
) -> dict:
    """Returns a complete MEJ place page object."""
    ...
```

### foundry_formatter.py

Core logic that reads lore entries and produces Foundry JSON:

```python
import json
import markdown   # pip install markdown (add to requirements.txt)
from .foundry_schemas import *
from .database import Database

class FoundryFormatter:
    def __init__(self, db: Database):
        self.db = db

    async def export_entry(
        self,
        slug: str,
        id_overrides: dict | None = None,
    ) -> dict:
        """Export a single lore entry as Foundry JSON."""
        entry = await self.db.get_entry(slug)
        if not entry:
            raise ValueError(f"Entry not found: {slug}")

        # Resolve cross-references for relationship objects
        references = await self.db.get_references(slug)
        relationships = []
        for ref in references:
            target = await self.db.get_entry(ref["target_slug"])
            if target:
                relationships.append(
                    build_relationship(
                        target_slug=ref["target_slug"],
                        target_name=target["name"],
                        target_type=ref["target_type"],
                        relationship_desc=ref.get("relationship", ""),
                    )
                )

        # Convert markdown content to HTML
        html_content = markdown.markdown(entry["content"])

        # Dispatch to type-specific formatter
        formatter_map = {
            "npc": self._format_npc,
            "location": self._format_location,
            "faction": self._format_faction,
            "event": self._format_event,
            "culture": self._format_culture,
        }
        formatter = formatter_map.get(entry["type"])
        if not formatter:
            raise ValueError(f"Unsupported type: {entry['type']}")

        foundry_json = formatter(entry, html_content, relationships)

        return {
            "slug": slug,
            "filename": f"fvtt-JournalEntry-{slug}.json",
            "json": json.dumps(foundry_json, indent=2),
            "type": entry["type"],
            "foundry_type": MEJ_PAGE_TYPES[entry["type"]],
        }

    def _format_npc(self, entry, html_content, relationships):
        """Format NPC lore entry as MEJ person journal."""
        metadata = json.loads(entry["metadata"])

        # Resolve location name from slug
        location_name = metadata.get("location_slug", "")
        # (async resolution happens in export_entry, passed via metadata)

        attributes = {
            "ancestry": "Human",  # Default, can be overridden
            "age": "",
            "eyes": "",
            "hair": "",
            "voice": "",
            "traits": metadata.get("appearance", ""),
            "ideals": "",
            "bonds": "",
            "flaws": "",
        }

        page = person_page(
            name=entry["name"],
            role=f"NPC - {entry['category'].title()}",
            location=location_name,
            attributes=attributes,
            html_content=html_content,
            relationships=relationships,
        )

        return journal_entry_envelope(
            name=entry["name"],
            page_type="person",
            pages=[page],
        )

    def _format_location(self, entry, html_content, relationships):
        """Format location lore entry as MEJ place journal."""
        metadata = json.loads(entry["metadata"])

        placetype_map = {
            "planet": "Planet",
            "moon": "Moon",
            "station": "Orbital Station",
            "settlement": "Settlement",
            "region": "Region",
        }

        attributes = {
            "age": "",
            "size": entry["category"].title(),
            "government": metadata.get("controlled_by", ""),
            "inhabitants": metadata.get("population", ""),
        }

        page = place_page(
            name=entry["name"],
            placetype=placetype_map.get(entry["category"], entry["category"].title()),
            location=metadata.get("parent_body", ""),
            attributes=attributes,
            html_content=html_content,
            relationships=relationships,
        )

        return journal_entry_envelope(
            name=entry["name"],
            page_type="place",
            pages=[page],
        )

    # _format_faction, _format_event, _format_culture follow same pattern
```

### MCP Tool Registration

Add to the existing `loremap/app/server.py`:

```python
@mcp.tool()
async def export_to_foundry(
    slug: str,
    include_related: bool = False,
    id_overrides: dict | None = None,
) -> dict:
    """Export a lore entry as Foundry VTT-importable JSON.

    Args:
        slug: The lore entry slug to export.
        include_related: If true, also exports all referenced entries.
        id_overrides: Optional map of slug → Foundry ID for entries
                      that already exist in the Foundry world.

    Returns:
        Dictionary with entries (list of exported JSON objects) and
        manifest (metadata about the export batch).
    """
    formatter = FoundryFormatter(db)
    entries = []
    id_map = {}

    # Export primary entry
    result = await formatter.export_entry(slug, id_overrides)
    entries.append(result)
    id_map[slug] = slug_to_foundry_id(slug)

    # Optionally export related entries
    if include_related:
        references = await db.get_references(slug)
        for ref in references:
            try:
                related = await formatter.export_entry(
                    ref["target_slug"], id_overrides
                )
                entries.append(related)
                id_map[ref["target_slug"]] = slug_to_foundry_id(
                    ref["target_slug"]
                )
            except ValueError:
                pass  # Skip entries that don't exist

    return {
        "entries": entries,
        "manifest": {
            "exported_at": datetime.now().isoformat(),
            "foundry_version": FOUNDRY_VERSION,
            "system": LANCER_SYSTEM_ID,
            "system_version": LANCER_SYSTEM_VERSION,
            "id_map": id_map,
        },
    }
```

### requirements.txt Addition

Add to `loremap/requirements.txt`:

```
markdown==3.7
```

---

## SMART EXPORT (CONVERSATION-ASSISTED)

The rigid field mapping above handles the structural transform, but
many Foundry fields benefit from intelligent extraction. For example,
a lore entry's content section might mention that an NPC has
"piercing green eyes" — which should populate `attributes.eyes`.

The conversation model can handle this at export time:

1. User says "export Cintra Gables to Foundry"
2. Orchestrator detects export intent
3. Orchestrator calls `get_entry("cintra-gables")` for full content
4. Orchestrator calls `get_foundry_schema("npc")` for field mapping
5. Conversation model receives both and produces enriched attributes
   by reading the full lore entry content
6. Enriched attributes are passed to the formatter alongside the
   structural data

This means the formatter has two modes:
- **Direct mode**: `export_to_foundry(slug)` — uses rigid mapping,
  fast, no model call required.
- **Smart mode**: triggered through conversation — model enriches
  the attributes before the formatter produces the final JSON.

Both produce valid Foundry JSON. Smart mode produces richer output.

---

## ACCEPTANCE TESTS

### Formatter
- [ ] NPC export produces valid JSON matching Cintra Gables structure
- [ ] Location export produces valid JSON matching Seicoe Station structure
- [ ] Location export produces valid JSON matching Seicoe Prime structure
- [ ] Cross-references use consistent placeholder IDs within a batch
- [ ] Batch export of connected entries (Cintra + Station + Prime)
      produces three JSON files with mutual relationship links
- [ ] Markdown content converts to clean HTML (format: 1)
- [ ] Generated JSON imports successfully into Foundry v12 via
      built-in import dialog
- [ ] MEJ renders imported person entries with populated attributes
- [ ] MEJ renders imported place entries with populated attributes
- [ ] Relationship links between imported entries resolve correctly
      when all entries in a batch are imported together

### MCP Tools
- [ ] `export_to_foundry` with single slug returns valid export
- [ ] `export_to_foundry` with `include_related=true` follows refs
- [ ] `export_batch_to_foundry` handles multiple slugs
- [ ] `get_foundry_schema` returns correct mapping for each type
- [ ] ID overrides correctly replace placeholder IDs

### Integration
- [ ] Conversation model can request and receive Foundry export
- [ ] Smart mode produces richer attributes than direct mode
- [ ] Export manifest correctly maps all slugs to IDs
- [ ] Non-existent slugs in references are skipped gracefully

---

## FUTURE EXTENSIONS

These are explicitly out of scope for this spec but are natural
next steps:

- **Actor export**: Lancer pilot and mech actor JSON (not journal
  entries — these are the mechanical character sheets). Requires
  deep understanding of the Lancer system's actor data model.
- **Roll table export**: Generate Foundry RollTable JSON from
  filtered lore queries (e.g., "random NPC from the Broken Clans").
- **Scene scaffolding**: Produce Scene JSON with token placements
  from location entries and their associated NPCs.
- **Import macro**: A Foundry macro that reads export manifests and
  batch-imports JSON files, resolving placeholder IDs to real
  Foundry document IDs and patching cross-references.
- **Reverse sync**: Import Foundry world data back into Lore Map
  to capture changes made directly in Foundry during sessions.
- **Foundry v13 support**: When Lancer system updates to v13,
  update schemas and test. The envelope structure may change.

---

## AGENT INSTRUCTIONS

If you are an AI agent building this:

1. This is an extension to the existing Lore Map MCP server. Do NOT
   create a new container or service.
2. Add files to `loremap/app/` only.
3. Add `markdown` to `loremap/requirements.txt`.
4. Register new MCP tools in the existing `server.py`.
5. Test against the three reference JSON exports (Cintra Gables,
   Seicoe Station, Seicoe Prime) as ground truth.
6. Generate placeholder IDs deterministically — same slug must
   always produce same ID.
7. The formatter must produce JSON that Foundry v12 accepts via
   its built-in "Import Data" dialog on JournalEntry documents.
8. Do not attempt to connect to a running Foundry instance.
9. If something in this spec is ambiguous, choose the simpler option.
10. Commit after completing the formatter and again after MCP tools.
