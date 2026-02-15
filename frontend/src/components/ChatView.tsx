import { useRef, useState } from 'react'

import type { Conversation, Message } from '../types'
import MessageInput from './MessageInput'
import MessageList from './MessageList'
import ModelSelector from './ModelSelector'

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
      <div className="flex items-center justify-between gap-2 border-b border-gray-800 px-4 py-3">
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

      {isLoadingMessages ? (
        <div className="flex flex-1 items-center justify-center text-sm text-gray-400">Loading messages...</div>
      ) : (
        <MessageList
          messages={messages}
          isStreaming={isStreaming}
          onQuickAction={(content) => void onSendMessage(content)}
          onQuote={handleQuote}
          onPin={onPin}
        />
      )}

      <MessageInput isStreaming={isStreaming} onSend={onSendMessage} onStop={onStopStreaming} quoteInsert={quoteInsert} />
    </div>
  )
}

export default ChatView
