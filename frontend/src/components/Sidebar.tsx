import type { Conversation } from '../types'

interface SidebarProps {
  conversations: Conversation[]
  activeConversationId: string | null
  isLoading: boolean
  onSelectConversation: (conversationId: string) => void
  onNewConversation: () => void
  onDeleteConversation: (conversationId: string) => void
  onOpenSettings: () => void
  onOpenLoreBrowser: () => void
}

function formatRelativeTime(timestamp: string): string {
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) {
    return 'Unknown'
  }

  const diffMs = Date.now() - date.getTime()
  const diffMinutes = Math.floor(diffMs / 60000)

  if (diffMinutes < 1) return 'Just now'
  if (diffMinutes < 60) return `${diffMinutes}m ago`

  const diffHours = Math.floor(diffMinutes / 60)
  if (diffHours < 24) return `${diffHours}h ago`

  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 7) return `${diffDays}d ago`

  return date.toLocaleDateString()
}

function Sidebar({
  conversations,
  activeConversationId,
  isLoading,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onOpenSettings,
  onOpenLoreBrowser,
}: SidebarProps) {
  return (
    <aside className="flex h-full w-full flex-col border-r border-gray-800 bg-gray-900">
      <div className="space-y-2 border-b border-gray-800 p-4">
        <button
          type="button"
          onClick={onNewConversation}
          className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-500"
        >
          New Chat
        </button>
        <button
          type="button"
          onClick={onOpenLoreBrowser}
          className="w-full rounded-md border border-gray-700 px-4 py-2 text-sm text-gray-200 transition hover:bg-gray-800"
        >
          Lore Browser
        </button>
        <button
          type="button"
          onClick={onOpenSettings}
          className="w-full rounded-md border border-gray-700 px-4 py-2 text-sm text-gray-200 transition hover:bg-gray-800"
        >
          Settings
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {isLoading ? (
          <p className="px-2 py-3 text-sm text-gray-400">Loading conversations...</p>
        ) : conversations.length === 0 ? (
          <p className="px-2 py-3 text-sm text-gray-400">No conversations yet.</p>
        ) : (
          <ul className="space-y-1">
            {conversations.map((conversation) => {
              const isActive = conversation.id === activeConversationId

              return (
                <li key={conversation.id} className="group">
                  <div
                    className={`flex items-center gap-1 rounded-md transition ${
                      isActive ? 'bg-gray-800 text-gray-100' : 'text-gray-300 hover:bg-gray-800/60 hover:text-gray-100'
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => onSelectConversation(conversation.id)}
                      className="flex-1 px-3 py-2 text-left"
                    >
                      <p className="truncate text-sm font-medium">{conversation.title}</p>
                      <p className="mt-1 text-xs text-gray-400">{formatRelativeTime(conversation.updated_at)}</p>
                    </button>
                    <button
                      type="button"
                      onClick={() => onDeleteConversation(conversation.id)}
                      className="mr-2 rounded px-2 py-1 text-xs text-red-300 opacity-100 transition hover:bg-red-950 md:opacity-0 md:group-hover:opacity-100"
                    >
                      Delete
                    </button>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </aside>
  )
}

export default Sidebar
