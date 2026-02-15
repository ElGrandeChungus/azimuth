import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  createConversation as createConversationRequest,
  deleteConversation as deleteConversationRequest,
  getConversation,
  getConversations,
  updateConversation,
} from '../api/client'
import type { Conversation, Message } from '../types'
import { useStream } from './useStream'

const TEMP_ASSISTANT_ID = 'temp-assistant-stream'

export function useChat() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [error, setError] = useState<string | null>(null)
  const [isLoadingConversations, setIsLoadingConversations] = useState<boolean>(true)
  const [isLoadingMessages, setIsLoadingMessages] = useState<boolean>(false)

  const { isStreaming, streamedContent, error: streamError, stream, stop } = useStream()

  const activeConversation = useMemo(
    () => conversations.find((conversation) => conversation.id === activeConversationId) ?? null,
    [conversations, activeConversationId],
  )

  const refresh = useCallback(async () => {
    setIsLoadingConversations(true)

    try {
      const list = await getConversations()
      setConversations(list)
      setActiveConversationId((current) => {
        if (current && list.some((conversation) => conversation.id === current)) {
          return current
        }
        return list[0]?.id ?? null
      })
      setError(null)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load conversations'
      setError(message)
    } finally {
      setIsLoadingConversations(false)
    }
  }, [])

  const loadConversationMessages = useCallback(async (conversationId: string) => {
    setIsLoadingMessages(true)

    try {
      const detail = await getConversation(conversationId)
      setMessages(detail.messages)
      setError(null)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load conversation'
      setError(message)
      setMessages([])
    } finally {
      setIsLoadingMessages(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    if (!activeConversationId) {
      setMessages([])
      return
    }

    void loadConversationMessages(activeConversationId)
  }, [activeConversationId, loadConversationMessages])

  useEffect(() => {
    if (streamError) {
      setError(streamError)
    }
  }, [streamError])

  const selectConversation = useCallback((conversationId: string) => {
    setActiveConversationId(conversationId)
  }, [])

  const createConversation = useCallback(async (): Promise<Conversation | null> => {
    try {
      const created = await createConversationRequest()
      setConversations((current) => [created, ...current])
      setActiveConversationId(created.id)
      setMessages([])
      setError(null)
      return created
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create conversation'
      setError(message)
      return null
    }
  }, [])

  const deleteConversation = useCallback(
    async (conversationId: string) => {
      try {
        await deleteConversationRequest(conversationId)
        setConversations((current) => {
          const filtered = current.filter((conversation) => conversation.id !== conversationId)
          if (activeConversationId === conversationId) {
            setActiveConversationId(filtered[0]?.id ?? null)
            setMessages([])
          }
          return filtered
        })
        setError(null)
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to delete conversation'
        setError(message)
      }
    },
    [activeConversationId],
  )

  const updateConversationModel = useCallback(async (conversationId: string, model: string) => {
    try {
      const updated = await updateConversation(conversationId, { model })
      setConversations((current) =>
        current.map((conversation) => (conversation.id === conversationId ? updated : conversation)),
      )
      setError(null)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update model'
      setError(message)
    }
  }, [])

  const sendMessage = useCallback(
    async (content: string) => {
      const trimmed = content.trim()
      if (!trimmed || isStreaming) {
        return
      }

      let targetConversationId = activeConversationId

      if (!targetConversationId) {
        const created = await createConversation()
        targetConversationId = created?.id ?? null
      }

      if (!targetConversationId) {
        return
      }

      const nowIso = new Date().toISOString()
      const tempUserMessage: Message = {
        id: `temp-user-${Date.now()}`,
        conversation_id: targetConversationId,
        role: 'user',
        content: trimmed,
        created_at: nowIso,
      }

      const tempAssistantMessage: Message = {
        id: TEMP_ASSISTANT_ID,
        conversation_id: targetConversationId,
        role: 'assistant',
        content: '',
        created_at: nowIso,
      }

      setMessages((current) => [...current, tempUserMessage, tempAssistantMessage])
      setError(null)

      const done = await stream(targetConversationId, trimmed, {
        onDelta: (delta) => {
          setMessages((current) =>
            current.map((message) =>
              message.id === TEMP_ASSISTANT_ID
                ? {
                    ...message,
                    content: message.content + delta,
                  }
                : message,
            ),
          )
        },
      })

      if (!done) {
        setMessages((current) => current.filter((message) => message.id !== TEMP_ASSISTANT_ID))
        return
      }

      setMessages((current) =>
        current.map((message) =>
          message.id === TEMP_ASSISTANT_ID
            ? {
                ...message,
                id: done.message_id,
                model: done.model,
              }
            : message,
        ),
      )

      const [conversationList, detail] = await Promise.all([
        getConversations(),
        getConversation(targetConversationId),
      ])
      setConversations(conversationList)
      setMessages(detail.messages)
    },
    [activeConversationId, createConversation, isStreaming, stream],
  )

  return {
    conversations,
    activeConversation,
    messages,
    isStreaming,
    streamedContent,
    error,
    isLoadingConversations,
    isLoadingMessages,
    selectConversation,
    createConversation,
    deleteConversation,
    updateConversationModel,
    sendMessage,
    stopStreaming: stop,
    refresh,
  }
}