import { useState } from 'react'

import ChatView from './components/ChatView'
import LoreBrowser from './components/LoreBrowser'
import SettingsPanel from './components/SettingsPanel'
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
    deleteConversation,
    updateConversationModel,
    sendMessage,
    stopStreaming,
  } = useChat()

  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false)
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [isLoreBrowserOpen, setIsLoreBrowserOpen] = useState(false)

  return (
    <div className="h-screen bg-gray-900 text-gray-100">
      <div className="flex h-full">
        <div className="hidden h-full w-80 flex-shrink-0 md:block">
          <Sidebar
            conversations={conversations}
            activeConversationId={activeConversation?.id ?? null}
            isLoading={isLoadingConversations}
            onSelectConversation={(id) => {
              selectConversation(id)
              setIsMobileSidebarOpen(false)
            }}
            onNewConversation={() => {
              void createConversation()
              setIsMobileSidebarOpen(false)
            }}
            onDeleteConversation={(id) => {
              void deleteConversation(id)
            }}
            onOpenLoreBrowser={() => {
              setIsLoreBrowserOpen(true)
              setIsMobileSidebarOpen(false)
            }}
            onOpenSettings={() => {
              setIsSettingsOpen(true)
              setIsMobileSidebarOpen(false)
            }}
          />
        </div>

        {isMobileSidebarOpen ? (
          <div className="fixed inset-0 z-30 md:hidden">
            <button
              type="button"
              onClick={() => setIsMobileSidebarOpen(false)}
              className="absolute inset-0 bg-black/60"
              aria-label="Close sidebar"
            />
            <div className="relative h-full w-80 max-w-[85vw]">
              <Sidebar
                conversations={conversations}
                activeConversationId={activeConversation?.id ?? null}
                isLoading={isLoadingConversations}
                onSelectConversation={(id) => {
                  selectConversation(id)
                  setIsMobileSidebarOpen(false)
                }}
                onNewConversation={() => {
                  void createConversation()
                  setIsMobileSidebarOpen(false)
                }}
                onDeleteConversation={(id) => {
                  void deleteConversation(id)
                }}
                onOpenLoreBrowser={() => {
                  setIsLoreBrowserOpen(true)
                  setIsMobileSidebarOpen(false)
                }}
                onOpenSettings={() => {
                  setIsSettingsOpen(true)
                  setIsMobileSidebarOpen(false)
                }}
              />
            </div>
          </div>
        ) : null}

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
            onChangeModel={(model) => {
              if (!activeConversation) {
                return
              }
              void updateConversationModel(activeConversation.id, model)
            }}
            onOpenSidebar={() => setIsMobileSidebarOpen(true)}
          />
        </main>
      </div>

      <SettingsPanel isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
      <LoreBrowser isOpen={isLoreBrowserOpen} onClose={() => setIsLoreBrowserOpen(false)} />
    </div>
  )
}

export default App
