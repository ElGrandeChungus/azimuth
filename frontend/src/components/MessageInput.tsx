import { useCallback, useEffect, useRef, useState } from 'react'
import type { ClipboardEvent as ReactClipboardEvent } from 'react'

import PasteSourcePrompt from './PasteSourcePrompt'

interface QuoteInsertRequest {
  id: number
  text: string
}

interface PendingPaste {
  text: string
  start: number
  end: number
}

interface MessageInputProps {
  isStreaming: boolean
  onSend: (content: string) => Promise<void>
  onStop: () => void
  quoteInsert?: QuoteInsertRequest | null
}

const LARGE_PASTE_THRESHOLD = 50
const PASTE_PROMPT_AUTO_DISMISS_MS = 5000
const PASTE_PROMPT_PREF_KEY = 'azimuth_skip_paste_source_prompt'

function toBlockquote(input: string): string {
  return input
    .split(/\r?\n/)
    .map((line) => `> ${line}`)
    .join('\n')
}

function buildReferenceBlock(label: string, text: string): string {
  const cleanedLabel = label.trim()
  const cleanedText = text.trim()
  return `[Reference from: ${cleanedLabel}]\n${cleanedText}\n[/Reference]`
}

function MessageInput({ isStreaming, onSend, onStop, quoteInsert = null }: MessageInputProps) {
  const [value, setValue] = useState('')
  const [pendingPaste, setPendingPaste] = useState<PendingPaste | null>(null)
  const [pasteSourceLabel, setPasteSourceLabel] = useState('')
  const [skipPastePrompt, setSkipPastePrompt] = useState(false)

  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const pastePromptTimerRef = useRef<number | null>(null)

  const clearPastePromptTimer = useCallback(() => {
    if (pastePromptTimerRef.current !== null) {
      window.clearTimeout(pastePromptTimerRef.current)
      pastePromptTimerRef.current = null
    }
  }, [])

  const resizeTextarea = useCallback(() => {
    const el = textareaRef.current
    if (!el) {
      return
    }

    el.style.height = 'auto'
    const lineHeight = 24
    const maxHeight = lineHeight * 6
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`
  }, [])

  const insertAtRange = useCallback((text: string, start: number, end: number) => {
    const insertion = text

    setValue((current) => {
      const safeStart = Math.max(0, Math.min(start, current.length))
      const safeEnd = Math.max(0, Math.min(end, current.length))

      const before = current.slice(0, safeStart)
      const after = current.slice(safeEnd)
      const next = `${before}${insertion}${after}`
      const cursor = before.length + insertion.length

      requestAnimationFrame(() => {
        const el = textareaRef.current
        if (!el) {
          return
        }
        el.focus()
        el.setSelectionRange(cursor, cursor)
      })

      return next
    })
  }, [])

  const applyPendingPasteAsIs = useCallback(() => {
    if (!pendingPaste) {
      return
    }

    insertAtRange(pendingPaste.text, pendingPaste.start, pendingPaste.end)
    setPendingPaste(null)
    setPasteSourceLabel('')
    clearPastePromptTimer()
  }, [clearPastePromptTimer, insertAtRange, pendingPaste])

  const applyPendingPasteWithLabel = useCallback(() => {
    if (!pendingPaste) {
      return
    }

    const label = pasteSourceLabel.trim()
    if (!label) {
      return
    }

    const wrapped = buildReferenceBlock(label, pendingPaste.text)
    insertAtRange(wrapped, pendingPaste.start, pendingPaste.end)
    setPendingPaste(null)
    setPasteSourceLabel('')
    clearPastePromptTimer()
  }, [clearPastePromptTimer, insertAtRange, pasteSourceLabel, pendingPaste])

  const insertQuoteAtCursor = useCallback((rawText: string) => {
    const text = rawText.trim()
    if (!text) {
      return
    }

    const textarea = textareaRef.current
    if (!textarea) {
      return
    }

    const start = textarea.selectionStart ?? 0
    const end = textarea.selectionEnd ?? 0

    setValue((current) => {
      const safeStart = Math.max(0, Math.min(start, current.length))
      const safeEnd = Math.max(0, Math.min(end, current.length))

      const before = current.slice(0, safeStart)
      const after = current.slice(safeEnd)

      const needsLeadingBreak = before.length > 0 && !before.endsWith('\n')
      const leadingBreak = needsLeadingBreak ? '\n\n' : ''
      const insertion = `${toBlockquote(text)}\n\n`

      const next = `${before}${leadingBreak}${insertion}${after}`
      const cursor = before.length + leadingBreak.length + insertion.length

      requestAnimationFrame(() => {
        const el = textareaRef.current
        if (!el) {
          return
        }
        el.focus()
        el.setSelectionRange(cursor, cursor)
      })

      return next
    })
  }, [])

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(PASTE_PROMPT_PREF_KEY)
      setSkipPastePrompt(raw === 'true')
    } catch {
      setSkipPastePrompt(false)
    }
  }, [])

  useEffect(() => {
    try {
      window.localStorage.setItem(PASTE_PROMPT_PREF_KEY, skipPastePrompt ? 'true' : 'false')
    } catch {
      // ignore localStorage failures
    }
  }, [skipPastePrompt])

  useEffect(() => {
    resizeTextarea()
  }, [value, resizeTextarea])

  const lastProcessedQuoteIdRef = useRef(-1)

  useEffect(() => {
    if (!quoteInsert || !quoteInsert.text.trim()) {
      return
    }

    if (quoteInsert.id <= lastProcessedQuoteIdRef.current) {
      return
    }

    lastProcessedQuoteIdRef.current = quoteInsert.id
    insertQuoteAtCursor(quoteInsert.text)
  }, [insertQuoteAtCursor, quoteInsert])

  useEffect(() => {
    if (!pendingPaste) {
      clearPastePromptTimer()
      return
    }

    clearPastePromptTimer()
    pastePromptTimerRef.current = window.setTimeout(() => {
      applyPendingPasteAsIs()
    }, PASTE_PROMPT_AUTO_DISMISS_MS)

    return () => {
      clearPastePromptTimer()
    }
  }, [applyPendingPasteAsIs, clearPastePromptTimer, pendingPaste])

  useEffect(() => {
    return () => {
      clearPastePromptTimer()
    }
  }, [clearPastePromptTimer])

  const submit = async () => {
    const trimmed = value.trim()
    if (!trimmed || isStreaming) {
      return
    }

    setValue('')
    await onSend(trimmed)
  }

  const handlePaste = (event: ReactClipboardEvent<HTMLTextAreaElement>) => {
    const pastedText = event.clipboardData.getData('text')
    if (!pastedText) {
      return
    }

    const textarea = textareaRef.current
    if (!textarea) {
      return
    }

    const start = textarea.selectionStart ?? value.length
    const end = textarea.selectionEnd ?? value.length

    if (skipPastePrompt || pastedText.trim().length <= LARGE_PASTE_THRESHOLD) {
      return
    }

    event.preventDefault()
    setPendingPaste({ text: pastedText, start, end })
    setPasteSourceLabel('')
  }

  return (
    <div className="border-t border-gray-800 bg-gray-900 p-4">
      <div className="mx-auto w-full max-w-3xl">
        <PasteSourcePrompt
          isVisible={pendingPaste !== null}
          label={pasteSourceLabel}
          onLabelChange={setPasteSourceLabel}
          dontAskAgain={skipPastePrompt}
          onToggleDontAskAgain={setSkipPastePrompt}
          onApplyLabel={applyPendingPasteWithLabel}
          onPastePlain={applyPendingPasteAsIs}
        />

        <div className="flex items-end gap-3">
          <textarea
            ref={textareaRef}
            rows={1}
            value={value}
            onChange={(event) => setValue(event.target.value)}
            onPaste={handlePaste}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                void submit()
              }
            }}
            placeholder="Type your message..."
            disabled={isStreaming}
            className="max-h-36 min-h-[44px] flex-1 resize-none rounded-md border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-gray-100 outline-none focus:border-blue-500"
          />

          {isStreaming ? (
            <button
              type="button"
              onClick={onStop}
              className="h-11 rounded-md border border-red-700 bg-red-900 px-4 text-sm font-semibold text-red-100 transition hover:bg-red-800"
            >
              Stop
            </button>
          ) : (
            <button
              type="button"
              onClick={() => {
                void submit()
              }}
              disabled={!value.trim()}
              className="h-11 rounded-md bg-blue-600 px-4 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-gray-700"
            >
              Send
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default MessageInput
