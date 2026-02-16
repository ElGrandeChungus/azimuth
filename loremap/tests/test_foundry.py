"""Tests for the Foundry Forge modules (foundry_schemas + foundry_formatter)."""

from __future__ import annotations

import json
import uuid

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# foundry_schemas tests (no DB required)
# ---------------------------------------------------------------------------
from app.foundry_schemas import (
    FOUNDRY_VERSION,
    LANCER_SYSTEM_ID,
    LANCER_SYSTEM_VERSION,
    MEJ_PAGE_TYPES,
    PLACETYPE_MAP,
    build_relationship,
    journal_entry_envelope,
    organization_page,
    person_page,
    place_page,
    slug_to_foundry_id,
    text_page,
)


class TestSlugToFoundryId:
    def test_deterministic(self):
        assert slug_to_foundry_id('cintra-gables') == slug_to_foundry_id('cintra-gables')

    def test_length(self):
        fid = slug_to_foundry_id('test-slug')
        assert len(fid) == 16

    def test_hex_chars(self):
        fid = slug_to_foundry_id('another-slug')
        assert all(c in '0123456789abcdef' for c in fid)

    def test_different_slugs(self):
        assert slug_to_foundry_id('alpha') != slug_to_foundry_id('beta')


class TestBuildRelationship:
    def test_basic(self):
        rel = build_relationship(
            target_slug='seicoe-station',
            target_name='Seicoe Station',
            target_type='location',
            relationship_desc='Lives at',
        )
        assert rel['name'] == 'Seicoe Station'
        assert rel['type'] == 'place'
        assert rel['relationship'] == 'Lives at'
        assert rel['id'] == slug_to_foundry_id('seicoe-station')
        assert rel['uuid'] == f"JournalEntry.{rel['id']}"
        assert rel['hidden'] is False

    def test_id_override(self):
        real_id = 'abc123def456ghij'
        rel = build_relationship(
            target_slug='seicoe-station',
            target_name='Seicoe Station',
            target_type='location',
            relationship_desc='Docked at',
            id_overrides={'seicoe-station': real_id},
        )
        assert rel['id'] == real_id
        assert rel['uuid'] == f'JournalEntry.{real_id}'

    def test_fallback_type(self):
        rel = build_relationship(
            target_slug='x', target_name='X',
            target_type='unknown_type', relationship_desc='',
        )
        assert rel['type'] == 'person'


class TestJournalEntryEnvelope:
    def test_required_keys(self):
        env = journal_entry_envelope('Test', 'person', [])
        assert env['name'] == 'Test'
        assert env['flags']['monks-enhanced-journal']['pagetype'] == 'person'
        assert env['flags']['exportSource']['system'] == LANCER_SYSTEM_ID
        assert env['flags']['exportSource']['coreVersion'] == FOUNDRY_VERSION
        assert env['folder'] is None
        assert '_stats' in env
        assert env['_stats']['systemVersion'] == LANCER_SYSTEM_VERSION


class TestPersonPage:
    def test_structure(self):
        page = person_page(
            slug='cintra-gables', name='Cintra Gables',
            role='NPC - Fixer', location='Seicoe Station',
            attributes={'traits': 'Tall'}, html_content='<p>Hello</p>',
            relationships=[],
        )
        assert page['type'] == 'text'
        flags = page['flags']['monks-enhanced-journal']
        assert flags['type'] == 'person'
        assert flags['role'] == 'NPC - Fixer'
        assert flags['location'] == 'Seicoe Station'
        assert page['text']['format'] == 1
        assert page['text']['content'] == '<p>Hello</p>'
        assert page['ownership']['default'] == -1
        assert len(page['_id']) == 16


class TestPlacePage:
    def test_structure(self):
        page = place_page(
            slug='seicoe-prime', name='Seicoe Prime',
            placetype='Planet', location='Taito System',
            attributes={'size': 'Large'}, html_content='<p>Big rock</p>',
            relationships=[],
        )
        flags = page['flags']['monks-enhanced-journal']
        assert flags['type'] == 'place'
        assert flags['placetype'] == 'Planet'
        assert page['text']['format'] == 1


class TestOrganizationPage:
    def test_structure(self):
        page = organization_page(
            slug='broken-clans', name='Broken Clans',
            attributes={'type': 'Clan'}, html_content='<p>Warriors</p>',
            relationships=[],
        )
        flags = page['flags']['monks-enhanced-journal']
        assert flags['type'] == 'organization'


class TestTextPage:
    def test_structure(self):
        page = text_page(
            slug='the-fall', name='The Fall',
            html_content='<p>Event</p>',
        )
        assert page['text']['format'] == 1
        assert page['flags'] == {}


# ---------------------------------------------------------------------------
# foundry_formatter tests (requires in-memory SQLite)
# ---------------------------------------------------------------------------
import aiosqlite

from app.database import SCHEMA_SQL
from app.foundry_formatter import FoundryFormatter, get_foundry_schema_info


@pytest_asyncio.fixture
async def test_db(monkeypatch, tmp_path):
    """Create an in-memory DB and patch get_db to use it."""
    db_path = str(tmp_path / 'test_lore.db')

    async def _patched_get_db():
        """Context manager yielding a connection to the test DB."""
        conn = await aiosqlite.connect(db_path)
        conn.row_factory = aiosqlite.Row
        await conn.execute('PRAGMA foreign_keys = ON')
        try:
            yield conn
        finally:
            await conn.close()

    from contextlib import asynccontextmanager
    patched = asynccontextmanager(_patched_get_db)
    monkeypatch.setattr('app.foundry_formatter.get_db', patched)

    # Initialise schema
    conn = await aiosqlite.connect(db_path)
    await conn.executescript(SCHEMA_SQL)
    await conn.commit()
    await conn.close()

    return db_path


async def _insert_entry(db_path, slug, entry_type, name, category, status, content, metadata=None):
    conn = await aiosqlite.connect(db_path)
    await conn.execute(
        '''INSERT INTO entries (id, slug, type, name, category, status, summary, content, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (str(uuid.uuid4()), slug, entry_type, name, category, status,
         f'Summary of {name}', content, json.dumps(metadata or {})),
    )
    await conn.commit()
    await conn.close()


async def _insert_reference(db_path, source_slug, target_slug, target_type, relationship=''):
    conn = await aiosqlite.connect(db_path)
    await conn.execute(
        '''INSERT INTO "references" (id, source_slug, target_slug, target_type, relationship)
           VALUES (?, ?, ?, ?, ?)''',
        (str(uuid.uuid4()), source_slug, target_slug, target_type, relationship),
    )
    await conn.commit()
    await conn.close()


class TestFormatterNpc:
    @pytest.mark.asyncio
    async def test_export_npc(self, test_db):
        await _insert_entry(
            test_db, 'cintra-gables', 'npc', 'Cintra Gables', 'civilian', 'alive',
            '# Cintra Gables\n\nA resourceful fixer on Seicoe Station.',
            {'location_slug': 'seicoe-station', 'appearance': 'Tall, sharp eyes', 'role': 'Fixer'},
        )
        await _insert_entry(
            test_db, 'seicoe-station', 'location', 'Seicoe Station', 'station', 'active',
            'An orbital station in the Taito System.',
        )
        await _insert_reference(test_db, 'cintra-gables', 'seicoe-station', 'location', 'Lives at')

        fmt = FoundryFormatter()
        result = await fmt.export_entry('cintra-gables')

        assert result['slug'] == 'cintra-gables'
        assert result['filename'] == 'fvtt-JournalEntry-cintra-gables.json'
        assert result['type'] == 'npc'
        assert result['foundry_type'] == 'person'

        doc = json.loads(result['json'])
        assert doc['name'] == 'Cintra Gables'
        assert doc['flags']['monks-enhanced-journal']['pagetype'] == 'person'

        page = doc['pages'][0]
        flags = page['flags']['monks-enhanced-journal']
        assert flags['type'] == 'person'
        assert 'NPC' in flags['role']
        assert flags['location'] == 'Seicoe Station'
        assert flags['attributes']['traits'] == 'Tall, sharp eyes'

        # Cross-reference
        assert len(flags['relationships']) == 1
        assert flags['relationships'][0]['name'] == 'Seicoe Station'
        assert flags['relationships'][0]['type'] == 'place'

        # HTML content
        assert page['text']['format'] == 1
        assert '<p>' in page['text']['content']


class TestFormatterLocation:
    @pytest.mark.asyncio
    async def test_export_location(self, test_db):
        await _insert_entry(
            test_db, 'seicoe-prime', 'location', 'Seicoe Prime', 'planet', 'active',
            'A rocky planet in the Taito System.',
            {'parent_body': 'Taito System', 'population': 'Sparse frontier settlements'},
        )

        fmt = FoundryFormatter()
        result = await fmt.export_entry('seicoe-prime')
        doc = json.loads(result['json'])

        assert doc['flags']['monks-enhanced-journal']['pagetype'] == 'place'
        page = doc['pages'][0]
        flags = page['flags']['monks-enhanced-journal']
        assert flags['placetype'] == 'Planet'
        assert flags['location'] == 'Taito System'
        assert flags['attributes']['inhabitants'] == 'Sparse frontier settlements'


class TestFormatterFaction:
    @pytest.mark.asyncio
    async def test_export_faction(self, test_db):
        await _insert_entry(
            test_db, 'broken-clans', 'faction', 'Broken Clans', 'clan', 'active',
            'A loose alliance of frontier clans.',
            {'allegiance': 'Independent', 'strength': 'Moderate'},
        )

        fmt = FoundryFormatter()
        result = await fmt.export_entry('broken-clans')
        doc = json.loads(result['json'])

        assert doc['flags']['monks-enhanced-journal']['pagetype'] == 'organization'
        page = doc['pages'][0]
        attrs = page['flags']['monks-enhanced-journal']['attributes']
        assert attrs['allegiance'] == 'Independent'
        assert attrs['type'] == 'Clan'


class TestFormatterEvent:
    @pytest.mark.asyncio
    async def test_export_event(self, test_db):
        await _insert_entry(
            test_db, 'the-fall', 'event', 'The Fall', 'battle', 'historical',
            'The catastrophic battle that ended the old order.',
            {'date_in_universe': '5014u', 'location_slug': 'seicoe-prime', 'key_actors': ['cintra-gables']},
        )
        await _insert_entry(
            test_db, 'seicoe-prime', 'location', 'Seicoe Prime', 'planet', 'active', 'A planet.',
        )
        await _insert_entry(
            test_db, 'cintra-gables', 'npc', 'Cintra Gables', 'civilian', 'alive', 'A person.',
        )

        fmt = FoundryFormatter()
        result = await fmt.export_entry('the-fall')
        doc = json.loads(result['json'])

        assert doc['flags']['monks-enhanced-journal']['pagetype'] == 'text'
        content = doc['pages'][0]['text']['content']
        assert '5014u' in content
        assert 'Seicoe Prime' in content
        assert 'Cintra Gables' in content


class TestFormatterCulture:
    @pytest.mark.asyncio
    async def test_export_culture(self, test_db):
        await _insert_entry(
            test_db, 'frontier-ways', 'culture', 'Frontier Ways', 'regional', 'active',
            'The customs of the frontier worlds.',
        )

        fmt = FoundryFormatter()
        result = await fmt.export_entry('frontier-ways')
        doc = json.loads(result['json'])
        assert doc['flags']['monks-enhanced-journal']['pagetype'] == 'text'


class TestFormatterBatch:
    @pytest.mark.asyncio
    async def test_batch_export(self, test_db):
        await _insert_entry(test_db, 'a', 'npc', 'A', 'civilian', 'alive', 'Person A.')
        await _insert_entry(test_db, 'b', 'npc', 'B', 'soldier', 'alive', 'Person B.')

        fmt = FoundryFormatter()
        result = await fmt.export_batch(['a', 'b'])

        assert len(result['entries']) == 2
        assert 'manifest' in result
        assert 'a' in result['manifest']['id_map']
        assert 'b' in result['manifest']['id_map']

    @pytest.mark.asyncio
    async def test_batch_skips_missing(self, test_db):
        await _insert_entry(test_db, 'exists', 'npc', 'Exists', 'civilian', 'alive', 'Here.')

        fmt = FoundryFormatter()
        result = await fmt.export_batch(['exists', 'no-such-slug'])

        assert len(result['entries']) == 1
        assert result['entries'][0]['slug'] == 'exists'


class TestFormatterWithRelated:
    @pytest.mark.asyncio
    async def test_export_with_related(self, test_db):
        await _insert_entry(
            test_db, 'cintra-gables', 'npc', 'Cintra Gables', 'civilian', 'alive',
            'A fixer.', {'location_slug': 'seicoe-station'},
        )
        await _insert_entry(
            test_db, 'seicoe-station', 'location', 'Seicoe Station', 'station', 'active',
            'A station.',
        )
        await _insert_reference(test_db, 'cintra-gables', 'seicoe-station', 'location', 'Lives at')

        fmt = FoundryFormatter()
        result = await fmt.export_with_related('cintra-gables')

        slugs_exported = [e['slug'] for e in result['entries']]
        assert 'cintra-gables' in slugs_exported
        assert 'seicoe-station' in slugs_exported
        assert len(result['manifest']['id_map']) == 2


class TestFormatterCrossRefConsistency:
    @pytest.mark.asyncio
    async def test_placeholder_ids_consistent(self, test_db):
        await _insert_entry(test_db, 'a', 'npc', 'A', 'civilian', 'alive', 'A.', {})
        await _insert_entry(test_db, 'b', 'location', 'B', 'station', 'active', 'B.', {})
        await _insert_reference(test_db, 'a', 'b', 'location', 'Located at')

        fmt = FoundryFormatter()
        result = await fmt.export_batch(['a', 'b'])

        # Entry A should reference entry B with B's placeholder ID
        doc_a = json.loads(result['entries'][0]['json'])
        rel = doc_a['pages'][0]['flags']['monks-enhanced-journal']['relationships'][0]
        expected_b_id = slug_to_foundry_id('b')
        assert rel['id'] == expected_b_id
        assert result['manifest']['id_map']['b'] == expected_b_id


class TestFormatterIdOverrides:
    @pytest.mark.asyncio
    async def test_override_replaces_placeholder(self, test_db):
        await _insert_entry(test_db, 'a', 'npc', 'A', 'civilian', 'alive', 'A.', {})
        await _insert_entry(test_db, 'b', 'location', 'B', 'station', 'active', 'B.', {})
        await _insert_reference(test_db, 'a', 'b', 'location', 'At')

        real_id = 'RealFoundryId1234'
        fmt = FoundryFormatter(id_overrides={'b': real_id})
        result = await fmt.export_entry('a')
        doc = json.loads(result['json'])
        rel = doc['pages'][0]['flags']['monks-enhanced-journal']['relationships'][0]
        assert rel['id'] == real_id


class TestGetFoundrySchemaInfo:
    def test_npc(self):
        info = get_foundry_schema_info('npc')
        assert 'schema' in info
        assert 'field_mapping' in info
        assert 'notes' in info
        assert info['schema']['mej_page_type'] == 'person'

    def test_location(self):
        info = get_foundry_schema_info('location')
        assert info['schema']['mej_page_type'] == 'place'

    def test_unsupported_type(self):
        with pytest.raises(ValueError):
            get_foundry_schema_info('spaceship')

    def test_all_types(self):
        for t in ('npc', 'location', 'faction', 'event', 'culture'):
            info = get_foundry_schema_info(t)
            assert info['schema']['foundry_version'] == FOUNDRY_VERSION


class TestFormatterNotFound:
    @pytest.mark.asyncio
    async def test_missing_slug_raises(self, test_db):
        fmt = FoundryFormatter()
        with pytest.raises(ValueError, match='Entry not found'):
            await fmt.export_entry('does-not-exist')
