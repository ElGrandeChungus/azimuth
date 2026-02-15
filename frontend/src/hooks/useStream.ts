import { useCallback, useEffect, useRef, useState } from 'react'

import { sendMessage } from '../api/client'
import type { StreamEvent } from '../types'

interface DonePayload {
  message_id: string
  model: string
}

function parseSseChunk(input: string): StreamEvent[] {
  const events: StreamEvent[] = []
  const rawEvents = input.split('\n\n')

  for (const rawEvent of rawEvents) {
    const lines = rawEvent
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line.length > 0)

    const dataLine = lines.find((line) => line.startsWith('data:'))
    if (!dataLine) {
      continue
    }

    const payloadText = dataLine.slice(5).trim()
    try {
      events.push(JSON.parse(payloadText) as StreamEvent)
    } catch {
      continue
    }
  }

  return events
}

export function useStream() {
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamedContent, setStreamedContent] = useState('')
  const [error, setError] = useState<string | null>(null)

  const abortControllerRef = useRef<AbortController | null>(null)

  const stop = useCallback(() => {
    abortControllerRef.current?.abort()
    abortControllerRef.current = null
    setIsStreaming(false)
  }, [])

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort()
    }
  }, [])

  const stream = useCallback(
    async (
      conversationId: string,
      content: string,
      handlers?: {
        onDelta?: (delta: string) => void
      },
    ): Promise<DonePayload | null> => {
      setIsStreaming(true)
      setStreamedContent('')
      setError(null)

      const controller = new AbortController()
      abortControllerRef.current = controller

      try {
        const response = await sendMessage(conversationId, content, controller.signal)
        const reader = response.body?.getReader()

        if (!reader) {
          throw new Error('Streaming response body is unavailable')
        }

        const decoder = new TextDecoder()
        let buffer = ''
        let donePayload: DonePayload | null = null

        while (true) {
          const { value, done } = await reader.read()
          if (done) {
            break
          }

          buffer += decoder.decode(value, { stream: true })

          const chunks = buffer.split('\n\n')
          buffer = chunks.pop() ?? ''

          for (const chunk of chunks) {
            const events = parseSseChunk(chunk)
            for (const event of events) {
              if (event.type === 'delta' && event.content) {
                setStreamedContent((current) => current + event.content!)
                handlers?.onDelta?.(event.content)
              }

              if (event.type === 'done' && event.message_id && event.model) {
                donePayload = {
                  message_id: event.message_id,
                  model: event.model,
                }
              }

              if (event.type === 'error') {
                throw new Error(event.message ?? 'Streaming error')
              }
            }
          }
        }

        return donePayload
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Streaming failed'
        if (!(err instanceof DOMException && err.name === 'AbortError')) {
          setError(message)
        }
        return null
      } finally {
        abortControllerRef.current = null
        setIsStreaming(false)
      }
    },
    [],
  )

  return {
    isStreaming,
    streamedContent,
    error,
    stream,
    stop,
  }
}
