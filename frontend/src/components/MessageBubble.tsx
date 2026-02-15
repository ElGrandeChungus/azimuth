import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { MouseEvent as ReactMouseEvent } from 'react'

import type { EntryReviewData, Message } from '../types'
import EntryReviewCard from './EntryReviewCard'
import SelectionPopover from './SelectionPopover'

interface MessageBubbleProps {
  message: Message
  onQuickAction?: (content: string) => void
  onQuote?: (selectedText: string) => void
  onPin?: (selectedText: string, messageId: string) => void
}

type PopoverPosition = {
  x: number
  y: number
  bottom: number
}

type SelectionPayload = {
  text: string
  rect: DOMRect
}

const MIN_SELECTION_LENGTH = 3
const MAX_SELECTION_LENGTH = 500
const SELECTION_DEBOUNCE_MS = 50
const LONG_PRESS_MS = 300
const MOBILE_SELECTION_DELAY_MS = 100
const COPY_FEEDBACK_MS = 1500

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

  text = text.replace(
    /```([\s\S]*?)```/g,
    '<div class="not-prose group relative my-2"><button type="button" data-copy-code-block="true" class="absolute right-2 top-2 z-10 inline-flex items-center rounded-md border border-gray-700 bg-gray-900/90 px-2 py-1 text-xs text-gray-200 transition hover:bg-gray-800 hover:text-white">Copy</button><pre class="overflow-x-auto rounded bg-gray-950 p-3 pt-10"><code>$1</code></pre></div>',
  )
  text = text.replace(
    /`([^`]+?)`/g,
    '<code data-inline-copy="true" class="cursor-pointer rounded border border-transparent bg-gray-950 px-1 py-0.5 text-xs transition hover:border-gray-700 hover:bg-gray-900">$1</code>',
  )
  text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  text = text.replace(/\*([^*]+)\*/g, '<em>$1</em>')
  text = text.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    '<a class="text-blue-300 underline" href="$2" target="_blank" rel="noreferrer">$1</a>',
  )

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

async function copyToClipboard(text: string): Promise<boolean> {
  if (!text || !navigator.clipboard || typeof navigator.clipboard.writeText !== 'function') {
    return false
  }

  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
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
    ? referencesRaw
      .filter((item) => item && typeof item === 'object')
      .map((item) => item as Record<string, unknown>)
      .map((item) => ({
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

function MessageBubble({ message, onQuickAction, onQuote, onPin }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const reviewData = !isUser ? extractEntryReview(message.content) : null

  const [showPopover, setShowPopover] = useState(false)
  const [selectedText, setSelectedText] = useState('')
  const [popoverPosition, setPopoverPosition] = useState<PopoverPosition>({ x: 0, y: 0, bottom: 0 })

  const bubbleRef = useRef<HTMLDivElement | null>(null)
  const contentRef = useRef<HTMLDivElement | null>(null)
  const popoverRef = useRef<HTMLDivElement | null>(null)
  const selectionTimerRef = useRef<number | null>(null)
  const longPressTimerRef = useRef<number | null>(null)
  const longPressTriggeredRef = useRef(false)
  const lastSelectionRef = useRef('')
  const copyTimerRefs = useRef<number[]>([])

  const isTouchDevice = useMemo(() => typeof window !== 'undefined' && 'ontouchstart' in window, [])

  const clearSelectionTimer = useCallback(() => {
    if (selectionTimerRef.current !== null) {
      window.clearTimeout(selectionTimerRef.current)
      selectionTimerRef.current = null
    }
  }, [])

  const clearLongPressTimer = useCallback(() => {
    if (longPressTimerRef.current !== null) {
      window.clearTimeout(longPressTimerRef.current)
      longPressTimerRef.current = null
    }
  }, [])

  const clearCopyTimers = useCallback(() => {
    for (const timerId of copyTimerRefs.current) {
      window.clearTimeout(timerId)
    }
    copyTimerRefs.current = []
  }, [])

  const queueCopyReset = useCallback((reset: () => void) => {
    const timerId = window.setTimeout(() => {
      reset()
      copyTimerRefs.current = copyTimerRefs.current.filter((id) => id !== timerId)
    }, COPY_FEEDBACK_MS)
    copyTimerRefs.current.push(timerId)
  }, [])

  const dismissPopover = useCallback(() => {
    setShowPopover(false)
    setSelectedText('')
    lastSelectionRef.current = ''
  }, [])

  const calculatePopoverPosition = useCallback((rect: DOMRect): PopoverPosition => {
    return {
      x: rect.left + rect.width / 2,
      y: rect.top,
      bottom: rect.bottom,
    }
  }, [])

  const readSelection = useCallback((): SelectionPayload | null => {
    const container = contentRef.current
    if (!container) {
      return null
    }

    const selection = window.getSelection()
    if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
      return null
    }

    const text = selection.toString().trim()
    if (text.length < MIN_SELECTION_LENGTH || text.length > MAX_SELECTION_LENGTH) {
      return null
    }

    const range = selection.getRangeAt(0)
    const startNode = range.startContainer
    const endNode = range.endContainer

    if (!container.contains(startNode) || !container.contains(endNode)) {
      return null
    }

    const rect = range.getBoundingClientRect()
    if (rect.width === 0 && rect.height === 0) {
      return null
    }

    return { text, rect }
  }, [])

  const handleSelection = useCallback(
    (extraDelay = 0) => {
      if (isUser || reviewData) {
        return
      }

      clearSelectionTimer()
      selectionTimerRef.current = window.setTimeout(() => {
        const payload = readSelection()
        if (!payload) {
          dismissPopover()
          return
        }

        if (showPopover && lastSelectionRef.current !== payload.text) {
          setShowPopover(false)
        }

        lastSelectionRef.current = payload.text
        setSelectedText(payload.text)
        setPopoverPosition(calculatePopoverPosition(payload.rect))
        setShowPopover(true)
      }, SELECTION_DEBOUNCE_MS + extraDelay)
    },
    [calculatePopoverPosition, clearSelectionTimer, dismissPopover, isUser, readSelection, reviewData, showPopover],
  )

  const handleMouseUp = useCallback(() => {
    handleSelection()
  }, [handleSelection])

  const handleTouchStart = useCallback(() => {
    if (!isTouchDevice || isUser || reviewData) {
      return
    }

    longPressTriggeredRef.current = false
    clearLongPressTimer()
    longPressTimerRef.current = window.setTimeout(() => {
      longPressTriggeredRef.current = true
    }, LONG_PRESS_MS)
  }, [clearLongPressTimer, isTouchDevice, isUser, reviewData])

  const handleTouchEnd = useCallback(() => {
    if (!isTouchDevice || isUser || reviewData) {
      return
    }

    clearLongPressTimer()
    if (longPressTriggeredRef.current) {
      handleSelection(MOBILE_SELECTION_DELAY_MS)
    }
  }, [clearLongPressTimer, handleSelection, isTouchDevice, isUser, reviewData])

  const handleTouchCancel = useCallback(() => {
    clearLongPressTimer()
    longPressTriggeredRef.current = false
  }, [clearLongPressTimer])

  const handleQuote = useCallback(() => {
    if (!selectedText) {
      return
    }

    onQuote?.(selectedText)
    dismissPopover()
    window.getSelection()?.removeAllRanges()
  }, [dismissPopover, onQuote, selectedText])

  const handlePin = useCallback(() => {
    if (!selectedText) {
      return
    }

    onPin?.(selectedText, message.id)
    dismissPopover()
    window.getSelection()?.removeAllRanges()
  }, [dismissPopover, message.id, onPin, selectedText])

  const handleContentClick = useCallback(
    async (event: ReactMouseEvent<HTMLDivElement>) => {
      const target = event.target as HTMLElement | null
      if (!target) {
        return
      }

      const blockButton = target.closest('button[data-copy-code-block="true"]') as HTMLButtonElement | null
      if (blockButton) {
        event.preventDefault()
        const codeNode = blockButton.parentElement?.querySelector('pre code') as HTMLElement | null
        const codeText = codeNode?.textContent ?? ''
        const copied = await copyToClipboard(codeText)
        if (!copied) {
          return
        }

        const originalLabel = blockButton.dataset.originalLabel ?? blockButton.textContent ?? 'Copy'
        blockButton.dataset.originalLabel = originalLabel
        blockButton.textContent = '? Copied'
        blockButton.classList.add('bg-emerald-600', 'text-white', 'border-emerald-500')

        queueCopyReset(() => {
          blockButton.textContent = blockButton.dataset.originalLabel ?? 'Copy'
          blockButton.classList.remove('bg-emerald-600', 'text-white', 'border-emerald-500')
        })
        return
      }

      const inlineCode = target.closest('code[data-inline-copy="true"]') as HTMLElement | null
      if (!inlineCode) {
        return
      }

      event.preventDefault()
      const inlineText = inlineCode.dataset.originalText ?? inlineCode.textContent ?? ''
      if (!inlineCode.dataset.originalText) {
        inlineCode.dataset.originalText = inlineText
      }

      const copied = await copyToClipboard(inlineText)
      if (!copied) {
        return
      }

      inlineCode.textContent = `${inlineText} ?`
      inlineCode.classList.add('text-emerald-300', 'border-emerald-500')

      queueCopyReset(() => {
        inlineCode.textContent = inlineCode.dataset.originalText ?? inlineText
        inlineCode.classList.remove('text-emerald-300', 'border-emerald-500')
      })
    },
    [queueCopyReset],
  )

  useEffect(() => {
    const handlePointerDown = (event: MouseEvent | TouchEvent) => {
      if (!showPopover) {
        return
      }

      const target = event.target as Node | null
      if (!target) {
        return
      }

      if (popoverRef.current?.contains(target)) {
        return
      }

      if (bubbleRef.current?.contains(target)) {
        return
      }

      dismissPopover()
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        dismissPopover()
      }
    }

    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('touchstart', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)

    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('touchstart', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [dismissPopover, showPopover])

  useEffect(() => {
    return () => {
      clearSelectionTimer()
      clearLongPressTimer()
      clearCopyTimers()
    }
  }, [clearCopyTimers, clearLongPressTimer, clearSelectionTimer])

  const popover =
    showPopover && !isUser && !reviewData
      ? createPortal(
        <SelectionPopover
          ref={popoverRef}
          isVisible={showPopover}
          position={popoverPosition}
          onQuote={handleQuote}
          onPin={handlePin}
          onDismiss={dismissPopover}
        />,
        document.body,
      )
      : null

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        ref={bubbleRef}
        className={`max-w-[85%] rounded-lg px-4 py-3 text-sm leading-relaxed ${isUser ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-100'
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
          <div
            ref={contentRef}
            className="prose prose-invert prose-sm max-w-none"
            onMouseUp={handleMouseUp}
            onTouchStart={handleTouchStart}
            onTouchEnd={handleTouchEnd}
            onTouchCancel={handleTouchCancel}
            onClick={handleContentClick}
            dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content) }}
          />
        ) : null}

        {!isUser && message.model ? <p className="mt-2 text-xs text-gray-400">{message.model}</p> : null}
      </div>
      {popover}
    </div>
  )
}

export default MessageBubble
