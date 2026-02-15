from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

EntryType = Literal['location', 'faction', 'npc', 'event', 'culture']


class EntryReference(BaseModel):
    id: str | None = None
    source_slug: str
    target_slug: str
    target_type: EntryType
    relationship: str | None = None


class BaseEntryMetadata(BaseModel):
    pass


class LocationMetadata(BaseEntryMetadata):
    parent_body: str = ''
    controlled_by: str = ''
    orbital_period: str = ''
    atmosphere: str = ''
    population: str = ''


class FactionMetadata(BaseEntryMetadata):
    allegiance: str = ''
    leader_slug: str = ''
    base_of_operations_slug: str = ''
    strength: str = ''
    resources: list[str] = Field(default_factory=list)


class NpcMetadata(BaseEntryMetadata):
    faction_slug: str = ''
    location_slug: str = ''
    disposition: str = ''
    role: str = ''
    appearance: str = ''
    secrets: list[str] = Field(default_factory=list)


class EventMetadata(BaseEntryMetadata):
    date_in_universe: str = ''
    location_slug: str = ''
    key_actors: list[str] = Field(default_factory=list)
    consequences: list[str] = Field(default_factory=list)


class CultureMetadata(BaseEntryMetadata):
    associated_faction_slug: str = ''
    associated_location_slug: str = ''
    values: list[str] = Field(default_factory=list)
    practices: list[str] = Field(default_factory=list)


class EntryBase(BaseModel):
    slug: str
    type: EntryType
    name: str
    category: str
    status: str
    parent_slug: str | None = None
    summary: str | None = None
    content: str


class LocationEntry(EntryBase):
    type: Literal['location'] = 'location'
    metadata: LocationMetadata


class FactionEntry(EntryBase):
    type: Literal['faction'] = 'faction'
    metadata: FactionMetadata


class NpcEntry(EntryBase):
    type: Literal['npc'] = 'npc'
    metadata: NpcMetadata


class EventEntry(EntryBase):
    type: Literal['event'] = 'event'
    metadata: EventMetadata


class CultureEntry(EntryBase):
    type: Literal['culture'] = 'culture'
    metadata: CultureMetadata


class EntryRecord(EntryBase):
    id: str
    metadata: dict
    created_at: datetime | str
    updated_at: datetime | str


class LexiconTerm(BaseModel):
    id: str
    term: str
    definition: str
    see_also: str | None = None
    created_at: datetime | str
    updated_at: datetime | str


class ThreadRecord(BaseModel):
    id: str
    entity_a: str
    entity_b: str
    relationship_type: str
    description: str
    relevant_entries: list[str] = Field(default_factory=list)
    created_at: datetime | str
    updated_at: datetime | str


class CampaignStateRecord(BaseModel):
    key: str
    value: str
    updated_at: datetime | str