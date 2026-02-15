from __future__ import annotations

from typing import Any

from app.database import get_db


def _tokenize(text: str) -> list[str]:
    import re

    return [
        t
        for t in re.findall(r'[a-zA-Z0-9]{3,}', text.lower())
        if t not in {'with', 'from', 'that', 'this', 'have', 'will', 'into'}
    ]


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


async def search_entries_payload(query: str, type: str | None = None, limit: int = 10) -> dict[str, Any]:
    query = query.strip()
    if not query:
        return {'results': []}

    safe_limit = max(1, min(int(limit), 50))
    conditions = ['entries_fts MATCH ?']
    params: list[Any] = [query]

    if type:
        conditions.append('e.type = ?')
        params.append(type)

    where_clause = ' AND '.join(conditions)
    params.append(safe_limit)

    async with get_db() as conn:
        cursor = await conn.execute(
            f'''
            SELECT e.slug, e.name, e.type, e.category, e.status, e.summary,
                   bm25(entries_fts) AS bm25_score
            FROM entries_fts
            JOIN entries e ON e.rowid = entries_fts.rowid
            WHERE {where_clause}
            ORDER BY bm25_score ASC
            LIMIT ?
            ''',
            tuple(params),
        )
        rows = await cursor.fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        bm25_score = float(row['bm25_score'])
        relevance = round(1.0 / (1.0 + max(0.0, bm25_score)), 4)
        results.append(
            {
                'slug': row['slug'],
                'name': row['name'],
                'type': row['type'],
                'category': row['category'],
                'status': row['status'],
                'summary': row['summary'],
                'relevance': relevance,
            }
        )

    return {'results': results}


async def find_related_payload(slug: str, limit: int = 5) -> dict[str, Any]:
    async with get_db() as conn:
        base_cursor = await conn.execute(
            'SELECT slug, name, summary, parent_slug FROM entries WHERE slug = ?',
            (slug,),
        )
        base = await base_cursor.fetchone()

    if base is None:
        raise ValueError(f'Entry not found: {slug}')

    safe_limit = max(1, min(int(limit), 25))
    related_map: dict[str, dict[str, Any]] = {}

    async with get_db() as conn:
        direct_out_cursor = await conn.execute(
            '''
            SELECT e.slug, e.name, e.type, e.category, e.status, e.summary
            FROM "references" r
            JOIN entries e ON e.slug = r.target_slug
            WHERE r.source_slug = ?
            ''',
            (slug,),
        )
        for row in await direct_out_cursor.fetchall():
            _merge_related(related_map, dict(row), 1.0, 'direct_reference')

        direct_in_cursor = await conn.execute(
            '''
            SELECT e.slug, e.name, e.type, e.category, e.status, e.summary
            FROM "references" r
            JOIN entries e ON e.slug = r.source_slug
            WHERE r.target_slug = ?
            ''',
            (slug,),
        )
        for row in await direct_in_cursor.fetchall():
            _merge_related(related_map, dict(row), 0.95, 'referenced_by')

        parent_slug = base['parent_slug']
        if parent_slug:
            same_parent_cursor = await conn.execute(
                '''
                SELECT slug, name, type, category, status, summary
                FROM entries
                WHERE parent_slug = ? AND slug != ?
                LIMIT 30
                ''',
                (parent_slug, slug),
            )
            for row in await same_parent_cursor.fetchall():
                _merge_related(related_map, dict(row), 0.72, 'shared_parent')

        shared_ref_cursor = await conn.execute(
            '''
            SELECT DISTINCT e.slug, e.name, e.type, e.category, e.status, e.summary
            FROM "references" r
            JOIN entries e ON e.slug = r.source_slug
            WHERE r.target_slug IN (
                SELECT target_slug FROM "references" WHERE source_slug = ?
            )
            AND r.source_slug != ?
            LIMIT 30
            ''',
            (slug, slug),
        )
        for row in await shared_ref_cursor.fetchall():
            _merge_related(related_map, dict(row), 0.63, 'shared_reference')

    query_terms = _tokenize(f"{base['name']} {base['summary'] or ''}")
    if query_terms:
        match_query = ' OR '.join(dict.fromkeys(query_terms[:8]))
        try:
            fts_results = await search_entries_payload(match_query, limit=20)
            for row in fts_results['results']:
                if row['slug'] != slug:
                    _merge_related(
                        related_map,
                        row,
                        max(0.35, float(row['relevance']) * 0.55),
                        'content_similarity',
                    )
        except Exception:
            pass

    filtered = [v for v in related_map.values() if v['slug'] != slug]
    filtered.sort(key=lambda item: (-float(item['score']), item['name'].lower()))
    return {'related': filtered[:safe_limit]}


async def validate_references_payload(slug: str | None = None) -> dict[str, Any]:
    conditions = ''
    params: tuple[Any, ...] = ()
    if slug:
        conditions = 'WHERE r.source_slug = ? OR r.target_slug = ?'
        params = (slug, slug)

    async with get_db() as conn:
        refs_cursor = await conn.execute(
            f'''
            SELECT r.source_slug, r.target_slug, r.target_type, r.relationship,
                   s.slug AS source_exists, t.slug AS target_exists
            FROM "references" r
            LEFT JOIN entries s ON s.slug = r.source_slug
            LEFT JOIN entries t ON t.slug = r.target_slug
            {conditions}
            ORDER BY r.source_slug, r.target_slug
            ''',
            params,
        )
        rows = await refs_cursor.fetchall()

        orphan_filter = ''
        orphan_params: tuple[Any, ...] = ()
        if slug:
            orphan_filter = 'WHERE e.slug = ?'
            orphan_params = (slug,)

        orphan_cursor = await conn.execute(
            f'''
            SELECT e.slug, e.name, e.type
            FROM entries e
            LEFT JOIN "references" r ON r.target_slug = e.slug
            {orphan_filter}
            GROUP BY e.slug, e.name, e.type
            HAVING COUNT(r.id) = 0
            ORDER BY e.name
            ''',
            orphan_params,
        )
        orphaned_entries = [dict(r) for r in await orphan_cursor.fetchall()]

    valid: list[dict[str, Any]] = []
    broken: list[dict[str, Any]] = []

    for row in rows:
        ref = {
            'source_slug': row['source_slug'],
            'target_slug': row['target_slug'],
            'target_type': row['target_type'],
            'relationship': row['relationship'],
        }
        if row['source_exists'] and row['target_exists']:
            valid.append(ref)
        else:
            broken.append(ref)

    return {'valid': valid, 'broken': broken, 'orphaned': orphaned_entries}
