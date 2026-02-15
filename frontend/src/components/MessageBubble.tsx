import type { Message } from '../types'

interface MessageBubbleProps {
  message: Message
}

function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[85%] rounded-lg px-4 py-3 text-sm leading-relaxed ${
          isUser ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-100'
        }`}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>
        {!isUser && message.model ? <p className="mt-2 text-xs text-gray-400">{message.model}</p> : null}
      </div>
    </div>
  )
}

export default MessageBubble