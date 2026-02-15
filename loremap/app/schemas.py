from __future__ import annotations

from typing import Any

ENTRY_SCHEMAS = {
    'location': {
        'categories': ['planet', 'moon', 'station', 'settlement', 'region'],
        'statuses': ['active', 'abandoned', 'contested', 'restricted'],
        'metadata': {
            'parent_body': '',
            'controlled_by': '',
            'orbital_period': '',
            'atmosphere': '',
            'population': '',
        },
    },
    'faction': {
        'categories': ['corporation', 'clan', 'government', 'insurgency', 'religious', 'military', 'other'],
        'statuses': ['active', 'dissolved', 'underground', 'rising', 'declining'],
        'metadata': {
            'allegiance': '',
            'leader_slug': '',
            'base_of_operations_slug': '',
            'strength': '',
            'resources': [],
        },
    },
    'npc': {
        'categories': ['leader', 'diplomat', 'soldier', 'civilian', 'criminal', 'scholar', 'other'],
        'statuses': ['alive', 'dead', 'missing', 'unknown'],
        'metadata': {
            'faction_slug': '',
            'location_slug': '',
            'disposition': '',
            'role': '',
            'appearance': '',
            'secrets': [],
        },
    },
    'event': {
        'categories': ['battle', 'political', 'disaster', 'discovery', 'cultural', 'personal'],
        'statuses': ['historical', 'ongoing', 'imminent', 'secret'],
        'metadata': {
            'date_in_universe': '',
            'location_slug': '',
            'key_actors': [],
            'consequences': [],
        },
    },
    'culture': {
        'categories': ['ethnic', 'regional', 'religious', 'professional', 'other'],
        'statuses': ['active', 'declining', 'extinct', 'evolving'],
        'metadata': {
            'associated_faction_slug': '',
            'associated_location_slug': '',
            'values': [],
            'practices': [],
        },
    },
}


def validate_entry_taxonomy(entry_type: str, category: str, status: str) -> list[str]:
    errors: list[str] = []

    schema = ENTRY_SCHEMAS.get(entry_type)
    if schema is None:
        return [f'Unsupported entry type: {entry_type}']

    if category not in schema['categories']:
        errors.append(f"Invalid category '{category}' for type '{entry_type}'")

    if status not in schema['statuses']:
        errors.append(f"Invalid status '{status}' for type '{entry_type}'")

    return errors


def default_metadata_for_type(entry_type: str) -> dict[str, Any]:
    schema = ENTRY_SCHEMAS.get(entry_type)
    if schema is None:
        raise ValueError(f'Unsupported entry type: {entry_type}')

    metadata = schema['metadata']
    return {key: (value.copy() if isinstance(value, list) else value) for key, value in metadata.items()}