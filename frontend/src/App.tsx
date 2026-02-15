import ChatView from './components/ChatView'
import Sidebar from './components/Sidebar'
import { useChat } from './hooks/useChat'

function App() {
  const {
    conversations,
    activeConversation,
    messages,
    isStreaming,
    error,
    isLoadingConversations,
    isLoadingMessages,
    selectConversation,
    createConversation,
    sendMessage,
    stopStreaming,
  } = useChat()

  return (
    <div className="h-screen bg-gray-900 text-gray-100">
      <div className="flex h-full flex-col md:flex-row">
        <div className="h-64 md:h-full md:w-80 md:flex-shrink-0">
          <Sidebar
            conversations={conversations}
            activeConversationId={activeConversation?.id ?? null}
            isLoading={isLoadingConversations}
            onSelectConversation={selectConversation}
            onNewConversation={() => {
              void createConversation()
            }}
          />
        </div>

        <main className="min-h-0 flex-1 bg-gray-950">
          {error ? (
            <div className="border-b border-red-900 bg-red-950 px-4 py-3 text-sm text-red-200">{error}</div>
          ) : null}
          <ChatView
            activeConversation={activeConversation}
            messages={messages}
            isStreaming={isStreaming}
            isLoadingMessages={isLoadingMessages}
            onSendMessage={sendMessage}
            onStopStreaming={stopStreaming}
          />
        </main>
      </div>
    </div>
  )
}

export default App