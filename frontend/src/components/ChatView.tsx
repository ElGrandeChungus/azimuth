import type { Conversation, Message } from '../types'
import MessageInput from './MessageInput'
import MessageList from './MessageList'

interface ChatViewProps {
  activeConversation: Conversation | null
  messages: Message[]
  isStreaming: boolean
  isLoadingMessages: boolean
  onSendMessage: (content: string) => Promise<void>
  onStopStreaming: () => void
}

function ChatView({
  activeConversation,
  messages,
  isStreaming,
  isLoadingMessages,
  onSendMessage,
  onStopStreaming,
}: ChatViewProps) {
  if (!activeConversation) {
    return (
      <div className="flex h-full items-center justify-center px-6 text-center text-gray-400">
        Start a new conversation
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-gray-800 px-4 py-3">
        <h2 className="text-sm font-semibold text-gray-100">{activeConversation.title}</h2>
      </div>

      {isLoadingMessages ? (
        <div className="flex flex-1 items-center justify-center text-sm text-gray-400">Loading messages...</div>
      ) : (
        <MessageList messages={messages} isStreaming={isStreaming} />
      )}

      <MessageInput isStreaming={isStreaming} onSend={onSendMessage} onStop={onStopStreaming} />
    </div>
  )
}

export default ChatView