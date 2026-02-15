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