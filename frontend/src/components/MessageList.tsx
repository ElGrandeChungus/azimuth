import { useEffect, useRef } from 'react'

import type { Message, PinnedContext } from '../types'
import MessageBubble from './MessageBubble'

interface MessageListProps {
  messages: Message[]
  isStreaming: boolean
  onQuickAction?: (content: string) => void
  onQuote?: (text: string) => void
  onPin?: (text: string, messageId: string) => void
  pinsByMessageId?: Record<string, PinnedContext[]>
  onUnpin?: (pinId: string) => void
}

function MessageList({ messages, isStreaming, onQuickAction, onQuote, onPin, pinsByMessageId = {}, onUnpin }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isStreaming])

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-3">
        {messages.map((message) => (
          <MessageBubble
            key={message.id}
            message={message}
            onQuickAction={onQuickAction}
            onQuote={onQuote}
            onPin={onPin}
            pinnedItems={pinsByMessageId[message.id] ?? []}
            onUnpinPin={onUnpin}
          />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

export default MessageList
