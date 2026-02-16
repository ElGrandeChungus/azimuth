"""Foundry VTT v12 JSON templates and constants for Monk's Enhanced Journal."""

from __future__ import annotations

import hashlib
import time
from typing import Any

# ---------------------------------------------------------------------------
# Version constants
# ---------------------------------------------------------------------------

FOUNDRY_VERSION = '12.343'
LANCER_SYSTEM_ID = 'lancer'
LANCER_SYSTEM_VERSION = '2.11.1'
EXPORT_WORLD_NAME = 'azimuth-export'

# ---------------------------------------------------------------------------
# MEJ page‑type mapping (lore entry type → MEJ pagetype)
# ---------------------------------------------------------------------------

MEJ_PAGE_TYPES: dict[str, str] = {
    'npc': 'person',
    'location': 'place',
    'faction': 'organization',
    'event': 'text',
    'culture': 'text',
}

# ---------------------------------------------------------------------------
# Location placetype mapping (lore category → display string)
# ---------------------------------------------------------------------------

PLACETYPE_MAP: dict[str, str] = {
    'planet': 'Planet',
    'moon': 'Moon',
    'station': 'Orbital Station',
    'settlement': 'Settlement',
    'region': 'Region',
}

# ---------------------------------------------------------------------------
# MEJ type mapping for relationship objects
# ---------------------------------------------------------------------------

_MEJ_REL_TYPE_MAP: dict[str, str] = {
    'npc': 'person',
    'location': 'place',
    'faction': 'organization',
    'event': 'person',      # no native MEJ type; fallback
    'culture': 'person',    # no native MEJ type; fallback
}

# ---------------------------------------------------------------------------
# Deterministic placeholder ID generation
# ---------------------------------------------------------------------------


def slug_to_foundry_id(slug: str) -> str:
    """Generate a deterministic 16-char hex ID from a slug.

    Foundry IDs are 16 alphanumeric chars. We use the first 16 hex digits
    of a SHA-256 hash so the same slug always produces the same ID.
    """
    return hashlib.sha256(slug.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Relationship object builder
# ---------------------------------------------------------------------------


def build_relationship(
    target_slug: str,
    target_name: str,
    target_type: str,
    relationship_desc: str,
    target_img: str = '',
    hidden: bool = False,
    id_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build a Foundry MEJ relationship object."""
    foundry_id = (id_overrides or {}).get(
        target_slug, slug_to_foundry_id(target_slug)
    )
    return {
        'id': foundry_id,
        'uuid': f'JournalEntry.{foundry_id}',
        'hidden': hidden,
        'name': target_name,
        'img': target_img,
        'type': _MEJ_REL_TYPE_MAP.get(target_type, 'person'),
        'relationship': relationship_desc,
    }


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_stats(now_ms: int | None = None) -> dict[str, Any]:
    ts = now_ms or int(time.time() * 1000)
    return {
        'coreVersion': FOUNDRY_VERSION,
        'systemId': LANCER_SYSTEM_ID,
        'systemVersion': LANCER_SYSTEM_VERSION,
        'createdTime': ts,
        'modifiedTime': ts,
        'lastModifiedBy': 'azimuth-export-00',
    }


def _page_id_from_slug(slug: str) -> str:
    """Derive a page-level 16-char ID distinct from the entry-level ID."""
    return hashlib.sha256(f'{slug}:page0'.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Document envelope
# ---------------------------------------------------------------------------


def journal_entry_envelope(
    name: str,
    page_type: str,
    pages: list[dict[str, Any]],
    header_img: str = '',
    now_ms: int | None = None,
) -> dict[str, Any]:
    """Build the outer JournalEntry structure."""
    return {
        'name': name,
        'flags': {
            'monks-enhanced-journal': {
                'pagetype': page_type,
                'img': header_img,
            },
            'exportSource': {
                'world': EXPORT_WORLD_NAME,
                'system': LANCER_SYSTEM_ID,
                'coreVersion': FOUNDRY_VERSION,
                'systemVersion': LANCER_SYSTEM_VERSION,
            },
        },
        'pages': pages,
        'folder': None,
        '_stats': _make_stats(now_ms),
    }


# ---------------------------------------------------------------------------
# Page templates
# ---------------------------------------------------------------------------


def person_page(
    slug: str,
    name: str,
    role: str,
    location: str,
    attributes: dict[str, str],
    html_content: str,
    relationships: list[dict[str, Any]],
    image_src: str = '',
    now_ms: int | None = None,
) -> dict[str, Any]:
    """Build a complete MEJ person page object."""
    return {
        'type': 'text',
        'name': name,
        'flags': {
            'monks-enhanced-journal': {
                'type': 'person',
                'role': role,
                'location': location,
                'attributes': attributes,
                'relationships': relationships,
            },
        },
        '_id': _page_id_from_slug(slug),
        'system': {},
        'title': {'show': True, 'level': 1},
        'image': {},
        'text': {
            'format': 1,
            'content': html_content,
        },
        'video': {'controls': True, 'volume': 0.5},
        'src': image_src,
        'sort': 0,
        'ownership': {'default': -1},
        '_stats': _make_stats(now_ms),
    }


def place_page(
    slug: str,
    name: str,
    placetype: str,
    location: str,
    attributes: dict[str, str],
    html_content: str,
    relationships: list[dict[str, Any]],
    image_src: str = '',
    now_ms: int | None = None,
) -> dict[str, Any]:
    """Build a complete MEJ place page object."""
    return {
        'type': 'text',
        'name': name,
        'flags': {
            'monks-enhanced-journal': {
                'type': 'place',
                'placetype': placetype,
                'location': location,
                'attributes': attributes,
                'relationships': relationships,
            },
        },
        '_id': _page_id_from_slug(slug),
        'system': {},
        'title': {'show': True, 'level': 1},
        'image': {},
        'text': {
            'format': 1,
            'content': html_content,
        },
        'video': {'controls': True, 'volume': 0.5},
        'src': image_src,
        'sort': 0,
        'ownership': {'default': -1},
        '_stats': _make_stats(now_ms),
    }


def organization_page(
    slug: str,
    name: str,
    attributes: dict[str, str],
    html_content: str,
    relationships: list[dict[str, Any]],
    image_src: str = '',
    now_ms: int | None = None,
) -> dict[str, Any]:
    """Build a complete MEJ organization page object."""
    return {
        'type': 'text',
        'name': name,
        'flags': {
            'monks-enhanced-journal': {
                'type': 'organization',
                'attributes': attributes,
                'relationships': relationships,
            },
        },
        '_id': _page_id_from_slug(slug),
        'system': {},
        'title': {'show': True, 'level': 1},
        'image': {},
        'text': {
            'format': 1,
            'content': html_content,
        },
        'video': {'controls': True, 'volume': 0.5},
        'src': image_src,
        'sort': 0,
        'ownership': {'default': -1},
        '_stats': _make_stats(now_ms),
    }


def text_page(
    slug: str,
    name: str,
    html_content: str,
    image_src: str = '',
    now_ms: int | None = None,
) -> dict[str, Any]:
    """Build a generic text page (events, cultures)."""
    return {
        'type': 'text',
        'name': name,
        'flags': {},
        '_id': _page_id_from_slug(slug),
        'system': {},
        'title': {'show': True, 'level': 1},
        'image': {},
        'text': {
            'format': 1,
            'content': html_content,
        },
        'video': {'controls': True, 'volume': 0.5},
        'src': image_src,
        'sort': 0,
        'ownership': {'default': -1},
        '_stats': _make_stats(now_ms),
    }
