import type { PinnedContext } from '../types'

interface PinnedContextPanelProps {
  pins: PinnedContext[]
  isLoading: boolean
  error: string | null
  onUnpin: (pinId: string) => void
}

const MAX_PINS = 10
const MAX_TOKENS = 2000

function truncate(input: string, max = 120): string {
  const normalized = input.replace(/\s+/g, ' ').trim()
  if (normalized.length <= max) {
    return normalized
  }
  return `${normalized.slice(0, max - 1)}…`
}

function PinnedContextPanel({ pins, isLoading, error, onUnpin }: PinnedContextPanelProps) {
  const totalTokens = pins.reduce((sum, pin) => sum + pin.token_estimate, 0)

  return (
    <div className="border-t border-gray-800 bg-gray-900 px-4 py-2">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-2">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-300">Pinned Context</p>
          <p className="text-xs text-gray-400">
            {pins.length}/{MAX_PINS} pins · {totalTokens}/{MAX_TOKENS} tokens
          </p>
        </div>

        {isLoading ? <p className="text-xs text-gray-400">Loading pinned context...</p> : null}
        {error ? <p className="rounded bg-red-950 px-2 py-1 text-xs text-red-200">{error}</p> : null}

        {!isLoading && pins.length === 0 ? <p className="text-xs text-gray-500">No pinned context for this conversation.</p> : null}

        {pins.length > 0 ? (
          <div className="max-h-28 space-y-1 overflow-y-auto pr-1">
            {pins.map((pin) => (
              <div key={pin.id} className="flex items-start justify-between gap-2 rounded border border-gray-800 bg-gray-950 px-2 py-1.5">
                <p className="text-xs text-gray-200">{truncate(pin.content)}</p>
                <button
                  type="button"
                  onClick={() => onUnpin(pin.id)}
                  className="shrink-0 rounded border border-gray-700 px-2 py-0.5 text-xs text-gray-300 transition hover:border-red-700 hover:bg-red-950 hover:text-red-200"
                >
                  Unpin
                </button>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  )
}

export default PinnedContextPanel
