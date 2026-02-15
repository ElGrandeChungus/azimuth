export interface Conversation {
  id: string
  title: string
  model: string
  updated_at: string
  message_count: number
}

export interface Message {
  id: string
  conversation_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  model?: string
  created_at: string
}

export interface PinnedContext {
  id: string
  conversation_id: string
  source_message_id?: string | null
  source_role?: 'user' | 'assistant' | 'system' | null
  content: string
  token_estimate: number
  created_at: string
}

export interface SystemPrompt {
  id: string
  name: string
  content: string
  is_default: boolean
}

export interface StreamEvent {
  type: 'delta' | 'done' | 'error'
  content?: string
  message_id?: string
  model?: string
  message?: string
}

export type LoreEntryType = 'location' | 'faction' | 'npc' | 'event' | 'culture'

export interface LoreReference {
  source_slug?: string
  target_slug: string
  target_type: LoreEntryType | string
  relationship?: string
  reason?: string
}

export interface LoreEntry {
  id: string
  slug: string
  type: LoreEntryType | string
  name: string
  category: string
  status: string
  parent_slug?: string | null
  summary?: string | null
  content?: string
  metadata?: Record<string, unknown>
  created_at?: string
  updated_at?: string
}

export interface LoreEntryListItem {
  slug: string
  name: string
  type: LoreEntryType | string
  category: string
  status: string
  summary?: string | null
  updated_at?: string
}

export interface EntrySchema {
  type: LoreEntryType | string
  required_fields: string[]
  optional_fields: string[]
  categories: string[]
  statuses: string[]
  metadata: Record<string, unknown>
  content_sections?: string[]
}

export interface LoreContextPackage {
  schema: EntrySchema
  filled_fields: Record<string, unknown>
  missing_required: string[]
  related_entries: Array<LoreEntryListItem & { score?: number; reasons?: string[] }>
  suggested_references: LoreReference[]
  follow_up_questions: string[]
}

export interface EntryReviewData {
  name: string
  type: LoreEntryType | string
  category: string
  status: string
  summary: string
  fields: Record<string, unknown>
  references: LoreReference[]
}
