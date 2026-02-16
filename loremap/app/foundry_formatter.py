"""Core formatting logic — reads lore entries and produces Foundry VTT JSON."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import markdown

from app.database import get_db
from app.foundry_schemas import (
    MEJ_PAGE_TYPES,
    FOUNDRY_VERSION,
    LANCER_SYSTEM_ID,
    LANCER_SYSTEM_VERSION,
    PLACETYPE_MAP,
    build_relationship,
    journal_entry_envelope,
    organization_page,
    person_page,
    place_page,
    slug_to_foundry_id,
    text_page,
)


# ---------------------------------------------------------------------------
# Internal data access helpers (mirrors patterns in server.py)
# ---------------------------------------------------------------------------


async def _load_entry(slug: str) -> dict[str, Any] | None:
    async with get_db() as conn:
        cursor = await conn.execute(
            '''
            SELECT id, slug, type, name, category, status, parent_slug,
                   summary, content, metadata, created_at, updated_at
            FROM entries
            WHERE slug = ?
            ''',
            (slug,),
        )
        row = await cursor.fetchone()

    if row is None:
        return None

    raw = row['metadata'] if 'metadata' in row.keys() else '{}'
    try:
        meta = json.loads(raw)
    except json.JSONDecodeError:
        meta = {}

    return {
        'id': row['id'],
        'slug': row['slug'],
        'type': row['type'],
        'name': row['name'],
        'category': row['category'],
        'status': row['status'],
        'parent_slug': row['parent_slug'],
        'summary': row['summary'],
        'content': row['content'],
        'metadata': meta,
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
    }


async def _load_references(slug: str) -> list[dict[str, Any]]:
    async with get_db() as conn:
        cursor = await conn.execute(
            '''
            SELECT source_slug, target_slug, target_type, relationship
            FROM "references"
            WHERE source_slug = ?
            ORDER BY target_slug ASC
            ''',
            (slug,),
        )
        return [dict(row) for row in await cursor.fetchall()]


async def _resolve_slug_to_name(slug: str) -> str:
    """Resolve a slug to its display name, returning the slug itself on miss."""
    async with get_db() as conn:
        cursor = await conn.execute(
            'SELECT name FROM entries WHERE slug = ? LIMIT 1',
            (slug,),
        )
        row = await cursor.fetchone()
    return row['name'] if row else slug


# ---------------------------------------------------------------------------
# Markdown → HTML
# ---------------------------------------------------------------------------

_md = markdown.Markdown(extensions=['extra', 'sane_lists'])


def _md_to_html(text: str) -> str:
    _md.reset()
    return _md.convert(text)


# ---------------------------------------------------------------------------
# FoundryFormatter
# ---------------------------------------------------------------------------


class FoundryFormatter:
    """Reads lore entries and produces Foundry VTT-importable JSON."""

    def __init__(self, id_overrides: dict[str, str] | None = None) -> None:
        self._id_overrides = id_overrides or {}
        self._now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def export_entry(self, slug: str) -> dict[str, Any]:
        """Export a single lore entry as Foundry JSON."""
        entry = await _load_entry(slug)
        if entry is None:
            raise ValueError(f'Entry not found: {slug}')

        # Resolve cross-references for relationship objects
        refs = await _load_references(slug)
        relationships: list[dict[str, Any]] = []
        for ref in refs:
            target = await _load_entry(ref['target_slug'])
            if target is None:
                continue
            relationships.append(
                build_relationship(
                    target_slug=ref['target_slug'],
                    target_name=target['name'],
                    target_type=ref['target_type'],
                    relationship_desc=ref.get('relationship', ''),
                    id_overrides=self._id_overrides,
                )
            )

        # Convert markdown content to HTML
        html_content = _md_to_html(entry['content'])

        # Dispatch to type-specific formatter
        formatter_map = {
            'npc': self._format_npc,
            'location': self._format_location,
            'faction': self._format_faction,
            'event': self._format_event,
            'culture': self._format_culture,
        }
        formatter = formatter_map.get(entry['type'])
        if formatter is None:
            raise ValueError(f"Unsupported entry type: {entry['type']}")

        foundry_json = await formatter(entry, html_content, relationships)
        foundry_type = MEJ_PAGE_TYPES[entry['type']]

        return {
            'slug': slug,
            'filename': f'fvtt-JournalEntry-{slug}.json',
            'json': json.dumps(foundry_json, indent=2),
            'type': entry['type'],
            'foundry_type': foundry_type,
        }

    async def export_batch(self, slugs: list[str]) -> dict[str, Any]:
        """Export multiple entries with a unified manifest."""
        entries: list[dict[str, Any]] = []
        id_map: dict[str, str] = {}

        for slug in slugs:
            try:
                result = await self.export_entry(slug)
                entries.append(result)
                id_map[slug] = self._id_overrides.get(
                    slug, slug_to_foundry_id(slug)
                )
            except ValueError:
                pass  # skip entries that don't exist

        return {
            'entries': entries,
            'manifest': self._build_manifest(id_map),
        }

    async def export_with_related(self, slug: str) -> dict[str, Any]:
        """Export an entry plus all entries it references."""
        # Start with the primary entry
        primary = await self.export_entry(slug)
        entries = [primary]
        id_map: dict[str, str] = {
            slug: self._id_overrides.get(slug, slug_to_foundry_id(slug)),
        }

        # Walk references
        refs = await _load_references(slug)
        seen = {slug}
        for ref in refs:
            target_slug = ref['target_slug']
            if target_slug in seen:
                continue
            seen.add(target_slug)
            try:
                related = await self.export_entry(target_slug)
                entries.append(related)
                id_map[target_slug] = self._id_overrides.get(
                    target_slug, slug_to_foundry_id(target_slug)
                )
            except ValueError:
                pass

        return {
            'entries': entries,
            'manifest': self._build_manifest(id_map),
        }

    # ------------------------------------------------------------------
    # Manifest
    # ------------------------------------------------------------------

    def _build_manifest(self, id_map: dict[str, str]) -> dict[str, Any]:
        return {
            'exported_at': datetime.now(timezone.utc).isoformat(),
            'foundry_version': FOUNDRY_VERSION,
            'system': LANCER_SYSTEM_ID,
            'system_version': LANCER_SYSTEM_VERSION,
            'id_map': id_map,
        }

    # ------------------------------------------------------------------
    # Type-specific formatters
    # ------------------------------------------------------------------

    async def _format_npc(
        self,
        entry: dict[str, Any],
        html_content: str,
        relationships: list[dict[str, Any]],
    ) -> dict[str, Any]:
        meta = entry['metadata']
        slug = entry['slug']

        # Resolve location name from slug
        location_name = ''
        loc_slug = meta.get('location_slug', '')
        if loc_slug:
            location_name = await _resolve_slug_to_name(loc_slug)

        attributes = {
            'ancestry': 'Human',
            'age': '',
            'eyes': '',
            'hair': '',
            'voice': '',
            'traits': meta.get('appearance', ''),
            'ideals': meta.get('disposition', ''),
            'bonds': '',
            'flaws': '',
        }

        role = meta.get('role', '') or entry['category']
        role_str = f'NPC - {role.title()}'

        page = person_page(
            slug=slug,
            name=entry['name'],
            role=role_str,
            location=location_name,
            attributes=attributes,
            html_content=html_content,
            relationships=relationships,
            now_ms=self._now_ms,
        )

        return journal_entry_envelope(
            name=entry['name'],
            page_type='person',
            pages=[page],
            now_ms=self._now_ms,
        )

    async def _format_location(
        self,
        entry: dict[str, Any],
        html_content: str,
        relationships: list[dict[str, Any]],
    ) -> dict[str, Any]:
        meta = entry['metadata']
        slug = entry['slug']

        placetype = PLACETYPE_MAP.get(
            entry['category'], entry['category'].title()
        )

        # Resolve controlled_by slug to a name
        gov = meta.get('controlled_by', '')
        if gov:
            gov = await _resolve_slug_to_name(gov)

        # Resolve parent body for location string
        location_str = meta.get('parent_body', '')

        attributes = {
            'age': '',
            'size': entry['category'].title(),
            'government': gov,
            'inhabitants': meta.get('population', ''),
        }

        page = place_page(
            slug=slug,
            name=entry['name'],
            placetype=placetype,
            location=location_str,
            attributes=attributes,
            html_content=html_content,
            relationships=relationships,
            now_ms=self._now_ms,
        )

        return journal_entry_envelope(
            name=entry['name'],
            page_type='place',
            pages=[page],
            now_ms=self._now_ms,
        )

    async def _format_faction(
        self,
        entry: dict[str, Any],
        html_content: str,
        relationships: list[dict[str, Any]],
    ) -> dict[str, Any]:
        meta = entry['metadata']
        slug = entry['slug']

        attributes: dict[str, str] = {
            'type': entry['category'].title(),
            'allegiance': meta.get('allegiance', ''),
            'strength': meta.get('strength', ''),
        }

        page = organization_page(
            slug=slug,
            name=entry['name'],
            attributes=attributes,
            html_content=html_content,
            relationships=relationships,
            now_ms=self._now_ms,
        )

        return journal_entry_envelope(
            name=entry['name'],
            page_type='organization',
            pages=[page],
            now_ms=self._now_ms,
        )

    async def _format_event(
        self,
        entry: dict[str, Any],
        html_content: str,
        relationships: list[dict[str, Any]],
    ) -> dict[str, Any]:
        meta = entry['metadata']
        slug = entry['slug']

        # Prepend date and location to HTML body
        header_parts: list[str] = []
        date_str = meta.get('date_in_universe', '')
        if date_str:
            header_parts.append(f'<p><strong>Date:</strong> {date_str}</p>')

        loc_slug = meta.get('location_slug', '')
        if loc_slug:
            loc_name = await _resolve_slug_to_name(loc_slug)
            header_parts.append(
                f'<p><strong>Location:</strong> {loc_name}</p>'
            )

        actors = meta.get('key_actors', [])
        if actors:
            resolved: list[str] = []
            for actor in actors:
                resolved.append(await _resolve_slug_to_name(actor))
            header_parts.append(
                '<p><strong>Key Actors:</strong> '
                + ', '.join(resolved)
                + '</p>'
            )

        if header_parts:
            html_content = '\n'.join(header_parts) + '\n<hr>\n' + html_content

        page = text_page(
            slug=slug,
            name=entry['name'],
            html_content=html_content,
            now_ms=self._now_ms,
        )

        return journal_entry_envelope(
            name=entry['name'],
            page_type='text',
            pages=[page],
            now_ms=self._now_ms,
        )

    async def _format_culture(
        self,
        entry: dict[str, Any],
        html_content: str,
        relationships: list[dict[str, Any]],
    ) -> dict[str, Any]:
        slug = entry['slug']

        page = text_page(
            slug=slug,
            name=entry['name'],
            html_content=html_content,
            now_ms=self._now_ms,
        )

        return journal_entry_envelope(
            name=entry['name'],
            page_type='text',
            pages=[page],
            now_ms=self._now_ms,
        )


# ---------------------------------------------------------------------------
# Foundry schema reference (for get_foundry_schema tool)
# ---------------------------------------------------------------------------

_FIELD_MAPPINGS: dict[str, dict[str, Any]] = {
    'npc': {
        'lore_fields': {
            'name': 'name + pages[0].name',
            'slug': 'filename: fvtt-JournalEntry-{slug}.json',
            'category': 'pages[0].flags.monks-enhanced-journal.role (prefixed NPC - )',
            'metadata.location_slug': 'pages[0].flags.monks-enhanced-journal.location (resolved to name)',
            'metadata.appearance': 'pages[0].flags.monks-enhanced-journal.attributes.traits',
            'metadata.disposition': 'pages[0].flags.monks-enhanced-journal.attributes.ideals',
            'metadata.secrets': 'Included in text.content body under secrets header',
            'metadata.role': 'Combined with category into role string',
            'content': 'pages[0].text.content (markdown → HTML)',
            'references': 'pages[0].flags.monks-enhanced-journal.relationships[]',
        },
        'notes': (
            'MEJ person attributes (ancestry, age, eyes, hair, voice, traits, '
            'ideals, bonds, flaws) are populated from metadata and content. '
            'Smart mode enriches these by having the conversation model extract '
            'details from the full lore entry content.'
        ),
    },
    'location': {
        'lore_fields': {
            'name': 'name + pages[0].name',
            'slug': 'filename: fvtt-JournalEntry-{slug}.json',
            'category': 'pages[0].flags.monks-enhanced-journal.placetype',
            'metadata.parent_body': 'pages[0].flags.monks-enhanced-journal.location',
            'metadata.controlled_by': 'pages[0].flags.monks-enhanced-journal.attributes.government (resolved to name)',
            'metadata.population': 'pages[0].flags.monks-enhanced-journal.attributes.inhabitants',
            'content': 'pages[0].text.content (markdown → HTML)',
            'references': 'pages[0].flags.monks-enhanced-journal.relationships[]',
        },
        'notes': (
            'Placetype is enriched from bare category to descriptive string '
            '(e.g. "Planet" → "Planet (Former Colony Site)"). The location '
            'field holds the parent context string.'
        ),
    },
    'faction': {
        'lore_fields': {
            'name': 'name + pages[0].name',
            'category': 'attributes.type',
            'metadata.allegiance': 'attributes.allegiance',
            'metadata.leader_slug': 'relationships[] (resolved to person)',
            'metadata.base_of_operations_slug': 'relationships[] (resolved to place)',
            'metadata.strength': 'attributes.strength',
            'content': 'pages[0].text.content (markdown → HTML)',
        },
        'notes': 'MEJ organization page type. Leader and base are rendered as relationship links.',
    },
    'event': {
        'lore_fields': {
            'name': 'name',
            'metadata.date_in_universe': 'Body header',
            'metadata.location_slug': 'Body reference (resolved to name)',
            'metadata.key_actors': 'Body list (resolved to names)',
            'content': 'pages[0].text.content (markdown → HTML)',
        },
        'notes': 'No dedicated MEJ page type. Exported as standard text journal with structured HTML body.',
    },
    'culture': {
        'lore_fields': {
            'name': 'name',
            'content': 'pages[0].text.content (markdown → HTML)',
        },
        'notes': 'No dedicated MEJ page type. Exported as standard text journal.',
    },
}


def get_foundry_schema_info(entry_type: str) -> dict[str, Any]:
    """Return annotated schema + field mapping for a given entry type."""
    mapping = _FIELD_MAPPINGS.get(entry_type)
    if mapping is None:
        raise ValueError(f'Unsupported entry type: {entry_type}')

    return {
        'schema': {
            'foundry_version': FOUNDRY_VERSION,
            'system': LANCER_SYSTEM_ID,
            'system_version': LANCER_SYSTEM_VERSION,
            'mej_page_type': MEJ_PAGE_TYPES.get(entry_type, 'text'),
            'envelope_keys': [
                'name', 'flags', 'pages', 'folder', '_stats',
            ],
            'page_keys': [
                'type', 'name', 'flags', '_id', 'system', 'title',
                'image', 'text', 'video', 'src', 'sort', 'ownership', '_stats',
            ],
        },
        'field_mapping': mapping['lore_fields'],
        'notes': mapping['notes'],
    }
