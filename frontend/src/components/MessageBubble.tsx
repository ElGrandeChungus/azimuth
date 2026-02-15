import type { EntryReviewData, Message } from '../types'
import EntryReviewCard from './EntryReviewCard'

interface MessageBubbleProps {
  message: Message
  onQuickAction?: (content: string) => void
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

function extractJsonBlock(content: string): unknown {
  const fenced = content.match(/```json\s*([\s\S]*?)```/i)
  const candidate = fenced ? fenced[1].trim() : content.trim()

  if (!(candidate.startsWith('{') && candidate.endsWith('}'))) {
    return null
  }

  try {
    return JSON.parse(candidate)
  } catch {
    return null
  }
}

function parseReviewFromJson(content: string): EntryReviewData | null {
  const parsed = extractJsonBlock(content)
  if (!parsed || typeof parsed !== 'object') {
    return null
  }

  const value = parsed as Record<string, unknown>
  const root = (value.entry && typeof value.entry === 'object' ? value.entry : value) as Record<string, unknown>

  const name = typeof root.name === 'string' ? root.name : ''
  const type = typeof root.type === 'string' ? root.type : ''
  const category = typeof root.category === 'string' ? root.category : ''
  const status = typeof root.status === 'string' ? root.status : ''
  const summary = typeof root.summary === 'string' ? root.summary : ''

  if (!name || !type || !category || !status) {
    return null
  }

  const fields = (root.fields && typeof root.fields === 'object' ? root.fields : root.metadata) as
    | Record<string, unknown>
    | undefined

  const referencesRaw = root.references
  const references = Array.isArray(referencesRaw)
    ? referencesRaw.filter((item) => item && typeof item === 'object').map((item) => item as Record<string, unknown>).map((item) => ({
        target_slug: String(item.target_slug ?? item.slug ?? ''),
        target_type: String(item.target_type ?? item.type ?? 'unknown'),
        relationship: item.relationship ? String(item.relationship) : undefined,
      }))
    : []

  return {
    name,
    type,
    category,
    status,
    summary,
    fields: fields ?? {},
    references,
  }
}

function parseReviewFromText(content: string): EntryReviewData | null {
  const find = (label: string) => {
    const regex = new RegExp(`(?:^|\\n)${label}:\\s*(.+)`, 'i')
    return content.match(regex)?.[1]?.trim() ?? ''
  }

  const name = find('name')
  const type = find('type')
  const category = find('category')
  const status = find('status')
  const summary = find('summary')

  if (!name || !type || !category || !status) {
    return null
  }

  return {
    name,
    type,
    category,
    status,
    summary,
    fields: {},
    references: [],
  }
}

function extractEntryReview(content: string): EntryReviewData | null {
  const jsonReview = parseReviewFromJson(content)
  if (jsonReview) {
    return jsonReview
  }

  return parseReviewFromText(content)
}

function MessageBubble({ message, onQuickAction }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const reviewData = !isUser ? extractEntryReview(message.content) : null

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[85%] rounded-lg px-4 py-3 text-sm leading-relaxed ${
          isUser ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-100'
        }`}
      >
        {isUser ? <p className="whitespace-pre-wrap">{message.content}</p> : null}

        {!isUser && reviewData && onQuickAction ? (
          <EntryReviewCard
            review={reviewData}
            onApprove={() => onQuickAction('I approve this entry. Save it.')}
            onEdit={() => onQuickAction('I want to edit this entry before saving.')}
            onReject={() => onQuickAction('I reject this entry. Do not save it.')}
          />
        ) : null}

        {!isUser && !reviewData ? (
          <div className="prose prose-invert prose-sm max-w-none" dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content) }} />
        ) : null}

        {!isUser && message.model ? <p className="mt-2 text-xs text-gray-400">{message.model}</p> : null}
      </div>
    </div>
  )
}

export default MessageBubble
