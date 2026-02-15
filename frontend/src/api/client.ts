import type { Conversation, Message, SystemPrompt } from '../types'

const API_URL = import.meta.env.VITE_API_URL ?? '/api'

type ModelsResponse = Array<{ id: string; name: string }>

type ConversationDetailResponse = {
  conversation: Conversation
  messages: Message[]
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  })

  const bodyText = await response.text()

  if (!response.ok) {
    throw new Error(bodyText || `Request failed with status ${response.status}`)
  }

  if (response.status === 204) {
    return undefined as T
  }

  const contentType = response.headers.get('content-type') ?? ''
  if (!contentType.toLowerCase().includes('application/json')) {
    const preview = bodyText.slice(0, 120)
    throw new Error(`Expected JSON response but received ${contentType || 'unknown content-type'}: ${preview}`)
  }

  try {
    return JSON.parse(bodyText) as T
  } catch {
    const preview = bodyText.slice(0, 120)
    throw new Error(`Invalid JSON response: ${preview}`)
  }
}

export async function getConversations(): Promise<Conversation[]> {
  return apiFetch<Conversation[]>('/conversations')
}

export async function createConversation(
  model?: string,
  systemPromptId?: string,
): Promise<Conversation> {
  return apiFetch<Conversation>('/conversations', {
    method: 'POST',
    body: JSON.stringify({
      model,
      system_prompt_id: systemPromptId,
    }),
  })
}

export async function getConversation(id: string): Promise<ConversationDetailResponse> {
  return apiFetch<ConversationDetailResponse>(`/conversations/${id}`)
}

export async function deleteConversation(id: string): Promise<void> {
  await apiFetch<void>(`/conversations/${id}`, {
    method: 'DELETE',
  })
}

export async function updateConversation(
  id: string,
  updates: Partial<Conversation>,
): Promise<Conversation> {
  return apiFetch<Conversation>(`/conversations/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  })
}

export async function sendMessage(
  conversationId: string,
  content: string,
  signal?: AbortSignal,
): Promise<Response> {
  const response = await fetch(`${API_URL}/conversations/${conversationId}/messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ content }),
    signal,
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `Request failed with status ${response.status}`)
  }

  return response
}

export async function getSettings(): Promise<Record<string, unknown>> {
  return apiFetch<Record<string, unknown>>('/settings')
}

export async function updateSettings(settings: Record<string, unknown>): Promise<void> {
  await apiFetch<void>('/settings', {
    method: 'PATCH',
    body: JSON.stringify(settings),
  })
}

export async function getModels(): Promise<ModelsResponse> {
  return apiFetch<ModelsResponse>('/settings/models')
}

export async function getSystemPrompts(): Promise<SystemPrompt[]> {
  return apiFetch<SystemPrompt[]>('/settings/prompts')
}

export async function createSystemPrompt(name: string, content: string): Promise<SystemPrompt> {
  return apiFetch<SystemPrompt>('/settings/prompts', {
    method: 'POST',
    body: JSON.stringify({ name, content }),
  })
}

export async function updateSystemPrompt(
  id: string,
  updates: Partial<SystemPrompt> & { is_default?: boolean },
): Promise<SystemPrompt> {
  return apiFetch<SystemPrompt>(`/settings/prompts/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  })
}

export async function deleteSystemPrompt(id: string): Promise<void> {
  await apiFetch<void>(`/settings/prompts/${id}`, {
    method: 'DELETE',
  })
}