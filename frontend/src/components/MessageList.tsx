import { useEffect, useRef } from 'react'

import type { Message } from '../types'
import MessageBubble from './MessageBubble'

interface MessageListProps {
  messages: Message[]
  isStreaming: boolean
  onQuickAction?: (content: string) => void
}

function MessageList({ messages, isStreaming, onQuickAction }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isStreaming])

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-3">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} onQuickAction={onQuickAction} />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

export default MessageList
