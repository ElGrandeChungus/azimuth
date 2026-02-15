import { useEffect, useMemo, useRef, useState } from 'react'

import { createPin, deletePin, getPins } from '../api/client'
import type { Conversation, Message, PinnedContext } from '../types'
import MessageInput from './MessageInput'
import MessageList from './MessageList'
import ModelSelector from './ModelSelector'
import PinnedContextPanel from './PinnedContextPanel'

interface ChatViewProps {
  activeConversation: Conversation | null
  messages: Message[]
  isStreaming: boolean
  isLoadingMessages: boolean
  onSendMessage: (content: string) => Promise<void>
  onStopStreaming: () => void
  onChangeModel: (model: string) => void
  onOpenSidebar: () => void
  onQuote?: (text: string) => void
  onPin?: (text: string, messageId: string) => void
}

type QuoteInsertRequest = {
  id: number
  text: string
}

function readErrorMessage(err: unknown, fallback: string): string {
  if (!(err instanceof Error)) {
    return fallback
  }

  try {
    const parsed = JSON.parse(err.message) as { detail?: unknown }
    if (parsed && typeof parsed.detail === 'string' && parsed.detail.trim()) {
      return parsed.detail
    }
  } catch {
    return err.message || fallback
  }

  return err.message || fallback
}

function ChatView({
  activeConversation,
  messages,
  isStreaming,
  isLoadingMessages,
  onSendMessage,
  onStopStreaming,
  onChangeModel,
  onOpenSidebar,
  onQuote,
  onPin,
}: ChatViewProps) {
  const [quoteInsert, setQuoteInsert] = useState<QuoteInsertRequest | null>(null)
  const quoteInsertCounterRef = useRef(0)

  const [pins, setPins] = useState<PinnedContext[]>([])
  const [isLoadingPins, setIsLoadingPins] = useState(false)
  const [pinsError, setPinsError] = useState<string | null>(null)

  useEffect(() => {
    if (!activeConversation) {
      setPins([])
      setPinsError(null)
      return
    }

    let cancelled = false

    const loadPins = async () => {
      setIsLoadingPins(true)
      try {
        const list = await getPins(activeConversation.id)
        if (!cancelled) {
          setPins(list)
          setPinsError(null)
        }
      } catch (err) {
        if (!cancelled) {
          const message = readErrorMessage(err, 'Failed to load pinned context')
          setPinsError(message)
          setPins([])
        }
      } finally {
        if (!cancelled) {
          setIsLoadingPins(false)
        }
      }
    }

    void loadPins()

    return () => {
      cancelled = true
    }
  }, [activeConversation])

  const handleQuote = (text: string) => {
    const cleaned = text.trim()
    if (!cleaned) {
      return
    }

    quoteInsertCounterRef.current += 1
    setQuoteInsert({
      id: quoteInsertCounterRef.current,
      text: cleaned,
    })

    onQuote?.(cleaned)
  }

  const handlePin = async (text: string, messageId: string) => {
    if (!activeConversation) {
      return
    }

    const cleaned = text.trim()
    if (!cleaned) {
      return
    }

    const source = messages.find((message) => message.id === messageId)

    try {
      const created = await createPin(activeConversation.id, {
        content: cleaned,
        source_message_id: messageId,
        source_role: source?.role,
      })
      setPins((current) => [created, ...current])
      setPinsError(null)
      onPin?.(cleaned, messageId)
    } catch (err) {
      const message = readErrorMessage(err, 'Failed to pin selected text')
      setPinsError(message)
    }
  }

  const handleUnpin = async (pinId: string) => {
    if (!activeConversation) {
      return
    }

    try {
      await deletePin(activeConversation.id, pinId)
      setPins((current) => current.filter((pin) => pin.id !== pinId))
      setPinsError(null)
    } catch (err) {
      const message = readErrorMessage(err, 'Failed to unpin context')
      setPinsError(message)
    }
  }

  const pinsByMessageId = useMemo(() => {
    const map: Record<string, PinnedContext[]> = {}
    for (const pin of pins) {
      const messageId = pin.source_message_id
      if (!messageId) {
        continue
      }

      if (!map[messageId]) {
        map[messageId] = []
      }
      map[messageId].push(pin)
    }
    return map
  }, [pins])

  if (!activeConversation) {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3 md:hidden">
          <button
            type="button"
            onClick={onOpenSidebar}
            className="rounded border border-gray-700 px-3 py-1 text-sm text-gray-200"
          >
            Menu
          </button>
        </div>
        <div className="flex h-full items-center justify-center px-6 text-center text-gray-400">
          Start a new conversation
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-gray-800">
        <div className="flex items-center justify-between gap-2 px-4 py-3">
          <div className="flex min-w-0 items-center gap-2">
            <button
              type="button"
              onClick={onOpenSidebar}
              className="rounded border border-gray-700 px-3 py-1 text-sm text-gray-200 md:hidden"
            >
              Menu
            </button>
            <h2 className="truncate text-sm font-semibold text-gray-100">{activeConversation.title}</h2>
          </div>
          <ModelSelector value={activeConversation.model ?? ''} onChange={onChangeModel} disabled={isStreaming} />
        </div>

        <PinnedContextPanel pins={pins} isLoading={isLoadingPins} error={pinsError} onUnpin={handleUnpin} />
      </div>

      {isLoadingMessages ? (
        <div className="flex flex-1 items-center justify-center text-sm text-gray-400">Loading messages...</div>
      ) : (
        <MessageList
          messages={messages}
          isStreaming={isStreaming}
          onQuickAction={(content) => void onSendMessage(content)}
          onQuote={handleQuote}
          onPin={handlePin}
          pinsByMessageId={pinsByMessageId}
          onUnpin={handleUnpin}
        />
      )}

      <MessageInput isStreaming={isStreaming} onSend={onSendMessage} onStop={onStopStreaming} quoteInsert={quoteInsert} />
    </div>
  )
}

export default ChatView
