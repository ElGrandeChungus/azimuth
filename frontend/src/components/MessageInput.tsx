import { useCallback, useEffect, useRef, useState } from 'react'

interface QuoteInsertRequest {
  id: number
  text: string
}

interface MessageInputProps {
  isStreaming: boolean
  onSend: (content: string) => Promise<void>
  onStop: () => void
  quoteInsert?: QuoteInsertRequest | null
}

function toBlockquote(input: string): string {
  return input
    .split(/\r?\n/)
    .map((line) => `> ${line}`)
    .join('\n')
}

function MessageInput({ isStreaming, onSend, onStop, quoteInsert = null }: MessageInputProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

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

  const insertQuoteAtCursor = useCallback((rawText: string) => {
    const text = rawText.trim()
    if (!text) {
      return
    }

    const textarea = textareaRef.current
    if (!textarea) {
      return
    }

    const start = textarea.selectionStart ?? value.length
    const end = textarea.selectionEnd ?? value.length

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
  }, [value.length])

  useEffect(() => {
    resizeTextarea()
  }, [value, resizeTextarea])

  useEffect(() => {
    if (!quoteInsert || !quoteInsert.text.trim()) {
      return
    }

    insertQuoteAtCursor(quoteInsert.text)
  }, [insertQuoteAtCursor, quoteInsert])

  const submit = async () => {
    const trimmed = value.trim()
    if (!trimmed || isStreaming) {
      return
    }

    setValue('')
    await onSend(trimmed)
  }

  return (
    <div className="border-t border-gray-800 bg-gray-900 p-4">
      <div className="mx-auto flex w-full max-w-3xl items-end gap-3">
        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          onChange={(event) => setValue(event.target.value)}
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
  )
}

export default MessageInput
