from __future__ import annotations

import json
import re
import uuid
from typing import Any

from fastmcp import FastMCP

from app.database import get_db, init_db_sync
from app.foundry_formatter import FoundryFormatter, get_foundry_schema_info
from app.foundry_schemas import slug_to_foundry_id
from app.schemas import ENTRY_SCHEMAS, default_metadata_for_type, validate_entry_taxonomy
from app.search import find_related_payload, search_entries_payload, validate_references_payload

mcp = FastMCP('Lore Map')


def _slugify(name: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return slug or 'entry'


def _first_sentence(text: str, max_len: int = 220) -> str:
    value = text.strip()
    if not value:
        return ''
    parts = re.split(r'(?<=[.!?])\s+', value)
    first = parts[0].strip() if parts else value
    return first[:max_len]


def _merge_related(existing: dict[str, dict[str, Any]], entry: dict[str, Any], score: float, reason: str) -> None:
    slug = entry['slug']
    current = existing.get(slug)
    if current is None:
        existing[slug] = {
            'slug': entry['slug'],
            'name': entry['name'],
            'type': entry['type'],
            'category': entry['category'],
            'status': entry['status'],
            'summary': entry.get('summary'),
            'score': round(score, 4),
            'reasons': [reason],
        }
        return

    if score > float(current['score']):
        current['score'] = round(score, 4)
    if reason not in current['reasons']:
        current['reasons'].append(reason)


async def _slug_exists(slug: str) -> bool:
    async with get_db() as conn:
        cursor = await conn.execute('SELECT 1 FROM entries WHERE slug = ? LIMIT 1', (slug,))
        row = await cursor.fetchone()
        return row is not None


async def _generate_unique_slug(name: str) -> str:
    base = _slugify(name)
    candidate = base
    counter = 2
    while await _slug_exists(candidate):
        candidate = f'{base}-{counter}'
        counter += 1
    return candidate


def _entry_from_row(row: Any) -> dict[str, Any]:
    metadata_raw = row['metadata'] if 'metadata' in row.keys() else '{}'
    try:
        metadata = json.loads(metadata_raw)
    except json.JSONDecodeError:
        metadata = {}

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
        'metadata': metadata,
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
    }


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

    return _entry_from_row(row)


async def _check_slug_exists(slug: str) -> bool:
    async with get_db() as conn:
        cursor = await conn.execute('SELECT 1 FROM entries WHERE slug = ? LIMIT 1', (slug,))
        return await cursor.fetchone() is not None


async def _validate_references(references: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    for ref in references:
        target_slug = str(ref.get('target_slug', '')).strip()
        if not target_slug:
            warnings.append('Reference missing target_slug')
            continue

        exists = await _check_slug_exists(target_slug)
        if not exists:
            warnings.append(f'Reference target does not exist: {target_slug}')

    return warnings


async def _get_entry_payload(slug: str) -> dict[str, Any]:
    entry = await _load_entry(slug)
    if entry is None:
        raise ValueError(f'Entry not found: {slug}')

    async with get_db() as conn:
        refs_cursor = await conn.execute(
            '''
            SELECT source_slug, target_slug, target_type, relationship
            FROM "references"
            WHERE source_slug = ?
            ORDER BY target_slug ASC
            ''',
            (slug,),
        )
        refs = [dict(row) for row in await refs_cursor.fetchall()]

        back_cursor = await conn.execute(
            '''
            SELECT source_slug, target_slug, target_type, relationship
            FROM "references"
            WHERE target_slug = ?
            ORDER BY source_slug ASC
            ''',
            (slug,),
        )
        referenced_by = [dict(row) for row in await back_cursor.fetchall()]

    return {
        'entry': entry,
        'references': refs,
        'referenced_by': referenced_by,
    }


async def _list_entries_payload(type: str | None = None, parent_slug: str | None = None) -> dict[str, Any]:
    conditions: list[str] = []
    params: list[Any] = []

    if type:
        conditions.append('type = ?')
        params.append(type)

    if parent_slug:
        conditions.append('parent_slug = ?')
        params.append(parent_slug)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ''

    async with get_db() as conn:
        cursor = await conn.execute(
            f'''
            SELECT slug, name, type, category, status, summary, updated_at
            FROM entries
            {where_clause}
            ORDER BY updated_at DESC, name ASC
            ''',
            tuple(params),
        )
        rows = await cursor.fetchall()

    return {'entries': [dict(row) for row in rows]}


async def _get_schema_payload(type: str) -> dict[str, Any]:
    schema = ENTRY_SCHEMAS.get(type)
    if schema is None:
        raise ValueError(f'Unsupported entry type: {type}')

    return {
        'schema': {
            'type': type,
            'required_fields': ['type', 'name', 'category', 'status', 'content'],
            'optional_fields': ['parent_slug', 'summary', 'metadata', 'references'],
            'categories': schema['categories'],
            'statuses': schema['statuses'],
            'metadata': schema['metadata'],
            'content_sections': ['Summary', 'Details', 'Hooks'],
        }
    }


async def _extract_filled_fields(entry_type: str, user_input: str, schema: dict[str, Any]) -> dict[str, Any]:
    text = user_input.strip()
    text_lower = text.lower()

    filled: dict[str, Any] = {'type': entry_type}

    quoted_match = re.search(r'"([^"]{2,80})"|\'([^\']{2,80})\'', text)
    if quoted_match:
        filled['name'] = (quoted_match.group(1) or quoted_match.group(2) or '').strip()
    else:
        patterns = [
            r'(?:named|called)\s+([A-Z][A-Za-z0-9\'\- ]{1,80})',
            rf'(?:add|create|make)\s+(?:an?\s+)?{re.escape(entry_type)}\s+([A-Z][A-Za-z0-9\'\- ]{{1,80}})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                filled['name'] = match.group(1).strip(' .,!?:;')
                break

    for value in schema['categories']:
        if re.search(rf'\b{re.escape(value.lower())}\b', text_lower):
            filled['category'] = value
            break

    for value in schema['statuses']:
        if re.search(rf'\b{re.escape(value.lower())}\b', text_lower):
            filled['status'] = value
            break

    summary = _first_sentence(text)
    if summary:
        filled['summary'] = summary

    if text:
        filled['content'] = text

    metadata_template = schema.get('metadata', {})
    metadata: dict[str, Any] = {}

    for key in metadata_template.keys():
        if key.endswith('_slug'):
            key_root = key[:-5].replace('_', ' ')
            named_match = re.search(rf'{re.escape(key_root)}\s*(?:is|:|=)\s*([A-Za-z0-9\'\- ]{{2,80}})', text_lower)
            if named_match:
                candidate = named_match.group(1).strip()
                search = await search_entries_payload(candidate, limit=1)
                if search['results']:
                    metadata[key] = search['results'][0]['slug']

    location_hint = re.search(r'\b(?:in|at|from|near)\s+(?:the\s+)?([A-Za-z][A-Za-z0-9\'\- ]{1,60})', text)
    if location_hint:
        candidate = location_hint.group(1).strip(' .,!?:;')
        search = await search_entries_payload(candidate, type='location', limit=1)
        if search['results']:
            if 'location_slug' in metadata_template:
                metadata['location_slug'] = search['results'][0]['slug']
            elif 'associated_location_slug' in metadata_template:
                metadata['associated_location_slug'] = search['results'][0]['slug']

    faction_hint = re.search(r'\b(?:for|with|aligned with|member of)\s+(?:the\s+)?([A-Za-z][A-Za-z0-9\'\- ]{1,60})', text)
    if faction_hint:
        candidate = faction_hint.group(1).strip(' .,!?:;')
        search = await search_entries_payload(candidate, type='faction', limit=1)
        if search['results']:
            if 'faction_slug' in metadata_template:
                metadata['faction_slug'] = search['results'][0]['slug']
            elif 'associated_faction_slug' in metadata_template:
                metadata['associated_faction_slug'] = search['results'][0]['slug']

    if metadata:
        filled['metadata'] = metadata

    return filled


def _build_follow_up_questions(schema: dict[str, Any], missing_required: list[str], filled_fields: dict[str, Any]) -> list[str]:
    questions: list[str] = []

    for field in missing_required:
        if field == 'name':
            questions.append('What is the entry name?')
        elif field == 'category':
            options = ', '.join(schema['categories'])
            questions.append(f'Which category fits best ({options})?')
        elif field == 'status':
            options = ', '.join(schema['statuses'])
            questions.append(f'What is the current status ({options})?')
        elif field == 'content':
            questions.append('Can you provide fuller details for Summary, Details, and Hooks?')

    metadata = filled_fields.get('metadata') if isinstance(filled_fields.get('metadata'), dict) else {}
    metadata_schema = schema.get('metadata', {})
    for key in metadata_schema.keys():
        if key.endswith('_slug') and not metadata.get(key):
            question_key = key.replace('_', ' ').replace(' slug', '')
            questions.append(f'Does this connect to an existing {question_key}? If so, which one?')

    deduped: list[str] = []
    for question in questions:
        if question not in deduped:
            deduped.append(question)
    return deduped[:8]


def _extract_search_terms(user_input: str) -> list[str]:
    terms: list[str] = []

    for match in re.findall(r'"([^"]{2,80})"|\'([^\']{2,80})\'', user_input):
        value = (match[0] or match[1]).strip()
        if value:
            terms.append(value)

    for match in re.findall(r'\b[A-Z][A-Za-z0-9\'\-]+(?:\s+[A-Z][A-Za-z0-9\'\-]+){0,2}\b', user_input):
        terms.append(match.strip())

    for match in re.findall(r'\b(?:in|at|from|near|for|with)\s+(?:the\s+)?([A-Za-z][A-Za-z0-9\'\- ]{1,60})', user_input):
        terms.append(match.strip(' .,!?:;'))

    deduped: list[str] = []
    for term in terms:
        norm = term.strip()
        if norm and norm.lower() not in [d.lower() for d in deduped]:
            deduped.append(norm)

    return deduped[:8]


async def _get_context_package_payload(
    entry_type: str,
    user_input: str,
    existing_slug: str | None = None,
) -> dict[str, Any]:
    schema_payload = await _get_schema_payload(entry_type)
    schema = schema_payload['schema']

    filled_fields = await _extract_filled_fields(entry_type, user_input, schema)

    missing_required: list[str] = []
    for field in schema['required_fields']:
        value = filled_fields.get(field)
        if value is None:
            missing_required.append(field)
            continue
        if isinstance(value, str) and not value.strip():
            missing_required.append(field)

    related_map: dict[str, dict[str, Any]] = {}

    terms = _extract_search_terms(user_input)
    for term in terms:
        try:
            matches = await search_entries_payload(term, limit=5)
        except Exception:
            continue

        for row in matches['results']:
            _merge_related(related_map, row, max(0.2, float(row['relevance'])), f'search_match:{term}')

    if existing_slug:
        try:
            related_from_existing = await find_related_payload(existing_slug, limit=8)
            for row in related_from_existing['related']:
                _merge_related(related_map, row, max(0.4, float(row.get('score', 0.0))), 'related_to_existing_entry')
        except ValueError:
            pass

    related_entries = list(related_map.values())
    related_entries.sort(key=lambda item: (-float(item['score']), item['name'].lower()))
    related_entries = related_entries[:10]

    suggested_references: list[dict[str, Any]] = []
    for row in related_entries[:5]:
        suggested_references.append(
            {
                'target_slug': row['slug'],
                'target_type': row['type'],
                'relationship': 'related_to',
                'reason': ', '.join(row.get('reasons', [])) or 'context_match',
            }
        )

    follow_up_questions = _build_follow_up_questions(schema, missing_required, filled_fields)

    return {
        'schema': schema,
        'filled_fields': filled_fields,
        'missing_required': missing_required,
        'related_entries': related_entries,
        'suggested_references': suggested_references,
        'follow_up_questions': follow_up_questions,
    }


@mcp.tool()
async def create_entry(
    type: str,
    name: str,
    category: str,
    status: str,
    summary: str,
    content: str,
    metadata: dict[str, Any] | None = None,
    references: list[dict[str, Any]] | None = None,
    parent_slug: str | None = None,
) -> dict[str, Any]:
    taxonomy_errors = validate_entry_taxonomy(type, category, status)
    if taxonomy_errors:
        raise ValueError('; '.join(taxonomy_errors))

    if parent_slug:
        parent_exists = await _check_slug_exists(parent_slug)
        if not parent_exists:
            raise ValueError(f'parent_slug does not exist: {parent_slug}')

    slug = await _generate_unique_slug(name)

    merged_metadata = default_metadata_for_type(type)
    if metadata:
        merged_metadata.update(metadata)

    references = references or []
    warnings = await _validate_references(references)

    entry_id = str(uuid.uuid4())

    async with get_db() as conn:
        await conn.execute(
            '''
            INSERT INTO entries (id, slug, type, name, category, status, parent_slug, summary, content, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                entry_id,
                slug,
                type,
                name,
                category,
                status,
                parent_slug,
                summary,
                content,
                json.dumps(merged_metadata),
            ),
        )

        for ref in references:
            target_slug = str(ref.get('target_slug', '')).strip()
            target_type = str(ref.get('target_type', '')).strip()
            relationship = ref.get('relationship')

            if not target_slug or not target_type:
                continue

            await conn.execute(
                '''
                INSERT OR REPLACE INTO "references" (id, source_slug, target_slug, target_type, relationship)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (str(uuid.uuid4()), slug, target_slug, target_type, relationship),
            )

        await conn.commit()

    entry = await _load_entry(slug)
    return {'entry': entry, 'warnings': warnings}


@mcp.tool()
async def get_entry(slug: str) -> dict[str, Any]:
    return await _get_entry_payload(slug)


@mcp.tool()
async def search_entries(query: str, type: str | None = None, limit: int = 10) -> dict[str, Any]:
    return await search_entries_payload(query=query, type=type, limit=limit)


@mcp.tool()
async def list_entries(type: str | None = None, parent_slug: str | None = None) -> dict[str, Any]:
    return await _list_entries_payload(type=type, parent_slug=parent_slug)


@mcp.tool()
async def update_entry(slug: str, updates: dict[str, Any]) -> dict[str, Any]:
    current = await _load_entry(slug)
    if current is None:
        raise ValueError(f'Entry not found: {slug}')

    next_type = str(updates.get('type', current['type']))
    next_category = str(updates.get('category', current['category']))
    next_status = str(updates.get('status', current['status']))

    taxonomy_errors = validate_entry_taxonomy(next_type, next_category, next_status)
    if taxonomy_errors:
        raise ValueError('; '.join(taxonomy_errors))

    if 'parent_slug' in updates and updates['parent_slug']:
        parent_exists = await _check_slug_exists(str(updates['parent_slug']))
        if not parent_exists:
            raise ValueError(f"parent_slug does not exist: {updates['parent_slug']}")

    references = updates.pop('references', None)
    warnings: list[str] = []

    allowed_columns = {
        'type': 'type',
        'name': 'name',
        'category': 'category',
        'status': 'status',
        'parent_slug': 'parent_slug',
        'summary': 'summary',
        'content': 'content',
        'metadata': 'metadata',
    }

    set_parts: list[str] = []
    params: list[Any] = []

    for key, value in updates.items():
        column = allowed_columns.get(key)
        if column is None:
            continue

        if key == 'metadata' and isinstance(value, dict):
            value = json.dumps(value)

        set_parts.append(f'{column} = ?')
        params.append(value)

    async with get_db() as conn:
        if set_parts:
            set_parts.append("updated_at = datetime('now')")
            params.append(slug)
            await conn.execute(
                f"UPDATE entries SET {', '.join(set_parts)} WHERE slug = ?",
                tuple(params),
            )

        if isinstance(references, list):
            warnings = await _validate_references(references)
            await conn.execute('DELETE FROM "references" WHERE source_slug = ?', (slug,))
            for ref in references:
                target_slug = str(ref.get('target_slug', '')).strip()
                target_type = str(ref.get('target_type', '')).strip()
                relationship = ref.get('relationship')
                if not target_slug or not target_type:
                    continue
                await conn.execute(
                    '''
                    INSERT OR REPLACE INTO "references" (id, source_slug, target_slug, target_type, relationship)
                    VALUES (?, ?, ?, ?, ?)
                    ''',
                    (str(uuid.uuid4()), slug, target_slug, target_type, relationship),
                )

        await conn.commit()

    entry = await _load_entry(slug)
    return {'entry': entry, 'warnings': warnings}


@mcp.tool()
async def delete_entry(slug: str) -> dict[str, Any]:
    async with get_db() as conn:
        inbound_cursor = await conn.execute(
            '''
            SELECT source_slug, target_slug, target_type, relationship
            FROM "references"
            WHERE target_slug = ?
            ORDER BY source_slug ASC
            ''',
            (slug,),
        )
        orphaned_references = [dict(row) for row in await inbound_cursor.fetchall()]

        delete_cursor = await conn.execute('DELETE FROM entries WHERE slug = ?', (slug,))
        deleted = delete_cursor.rowcount > 0

        await conn.commit()

    return {'deleted': deleted, 'orphaned_references': orphaned_references}


@mcp.tool()
async def get_schema(type: str) -> dict[str, Any]:
    return await _get_schema_payload(type)


@mcp.tool()
async def find_related(slug: str, limit: int = 5) -> dict[str, Any]:
    return await find_related_payload(slug=slug, limit=limit)


@mcp.tool()
async def validate_references(slug: str | None = None) -> dict[str, Any]:
    return await validate_references_payload(slug=slug)


@mcp.tool()
async def get_context_package(
    entry_type: str,
    user_input: str,
    existing_slug: str | None = None,
) -> dict[str, Any]:
    return await _get_context_package_payload(
        entry_type=entry_type,
        user_input=user_input,
        existing_slug=existing_slug,
    )


@mcp.tool()
async def export_to_foundry(
    slug: str,
    include_related: bool = False,
    id_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
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
    formatter = FoundryFormatter(id_overrides=id_overrides)
    if include_related:
        return await formatter.export_with_related(slug)

    result = await formatter.export_entry(slug)
    return {
        'entries': [result],
        'manifest': formatter._build_manifest(
            {slug: (id_overrides or {}).get(slug, slug_to_foundry_id(slug))}
        ),
    }


@mcp.tool()
async def export_batch_to_foundry(
    slugs: list[str],
    id_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Export multiple lore entries as Foundry VTT-importable JSON.

    Args:
        slugs: List of lore entry slugs to export.
        id_overrides: Optional map of slug → Foundry ID for entries
                      that already exist in the Foundry world.

    Returns:
        Dictionary with entries (list of exported JSON objects) and
        manifest (metadata about the export batch).
    """
    formatter = FoundryFormatter(id_overrides=id_overrides)
    return await formatter.export_batch(slugs)


@mcp.tool()
async def get_foundry_schema(entry_type: str) -> dict[str, Any]:
    """Return annotated Foundry JSON template and field mapping guidance.

    Args:
        entry_type: One of 'npc', 'location', 'faction', 'event', 'culture'.

    Returns:
        Dictionary with schema (Foundry structure overview),
        field_mapping (lore field → Foundry field), and notes.
    """
    return get_foundry_schema_info(entry_type)


@mcp.resource('lore://schemas/{type}')
async def resource_schema(type: str) -> dict[str, Any]:
    return await _get_schema_payload(type)


@mcp.resource('lore://entries/{slug}')
async def resource_entry(slug: str) -> dict[str, Any]:
    return await _get_entry_payload(slug)


@mcp.resource('lore://index/{type}')
async def resource_index(type: str) -> dict[str, Any]:
    return await _list_entries_payload(type=type)


def main() -> None:
    init_db_sync()
    mcp.run(
        transport='streamable-http',
        host='0.0.0.0',
        port=8001,
        path='/mcp',
        log_level='info',
    )


if __name__ == '__main__':
    main()
