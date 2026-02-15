import type { Message } from '../types'

interface MessageBubbleProps {
  message: Message
}

function escapeHtml(input: string): string {
  return input
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function renderMarkdown(content: string): string {
  let text = escapeHtml(content)

  text = text.replace(/```([\s\S]*?)```/g, '<pre class="my-2 overflow-x-auto rounded bg-gray-950 p-3"><code>$1</code></pre>')
  text = text.replace(/`([^`]+?)`/g, '<code class="rounded bg-gray-950 px-1 py-0.5 text-xs">$1</code>')
  text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  text = text.replace(/\*([^*]+)\*/g, '<em>$1</em>')
  text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a class="text-blue-300 underline" href="$2" target="_blank" rel="noreferrer">$1</a>')

  const lines = text.split('\n')
  const renderedLines: string[] = []
  let inList = false

  for (const line of lines) {
    if (/^\s*[-*]\s+/.test(line)) {
      if (!inList) {
        renderedLines.push('<ul class="my-2 list-disc pl-5">')
        inList = true
      }
      renderedLines.push(`<li>${line.replace(/^\s*[-*]\s+/, '')}</li>`)
      continue
    }

    if (inList) {
      renderedLines.push('</ul>')
      inList = false
    }

    renderedLines.push(line)
  }

  if (inList) {
    renderedLines.push('</ul>')
  }

  return renderedLines.join('<br />')
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
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="prose prose-invert prose-sm max-w-none" dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content) }} />
        )}
        {!isUser && message.model ? <p className="mt-2 text-xs text-gray-400">{message.model}</p> : null}
      </div>
    </div>
  )
}

export default MessageBubble