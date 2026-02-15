import { forwardRef, useLayoutEffect, useState } from 'react'

type PopoverPosition = {
  x: number
  y: number
  bottom: number
}

interface SelectionPopoverProps {
  isVisible: boolean
  position: PopoverPosition
  onQuote: () => void
  onPin: () => void
  onDismiss: () => void
}

const VIEWPORT_MARGIN = 10
const POPOVER_OFFSET = 10

type ComputedPosition = {
  left: number
  top: number
}

const SelectionPopover = forwardRef<HTMLDivElement, SelectionPopoverProps>(function SelectionPopover(
  { isVisible, position, onQuote, onPin, onDismiss },
  ref,
) {
  const [computed, setComputed] = useState<ComputedPosition>({
    left: position.x,
    top: position.y,
  })

  useLayoutEffect(() => {
    if (!isVisible) {
      return
    }

    const element = ref && typeof ref !== 'function' ? ref.current : null
    if (!element) {
      return
    }

    const rect = element.getBoundingClientRect()

    let left = position.x - rect.width / 2
    left = Math.max(VIEWPORT_MARGIN, Math.min(left, window.innerWidth - rect.width - VIEWPORT_MARGIN))

    let top = position.y - rect.height - POPOVER_OFFSET
    if (top < VIEWPORT_MARGIN) {
      top = position.bottom + POPOVER_OFFSET
    }
    if (top + rect.height > window.innerHeight - VIEWPORT_MARGIN) {
      top = Math.max(VIEWPORT_MARGIN, window.innerHeight - rect.height - VIEWPORT_MARGIN)
    }

    setComputed({ left, top })
  }, [isVisible, position.x, position.y, position.bottom, ref])

  return (
    <div
      ref={ref}
      role="toolbar"
      aria-hidden={!isVisible}
      className="fixed z-[70] flex gap-2 rounded-lg border border-gray-700 bg-gray-800 px-2 py-1.5 shadow-lg"
      style={{
        left: `${computed.left}px`,
        top: `${computed.top}px`,
        visibility: isVisible ? 'visible' : 'hidden',
      }}
    >
      <button
        type="button"
        onClick={onQuote}
        className="rounded px-3 py-1.5 text-sm text-gray-100 transition-all duration-150 hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
        aria-label="Quote selected text"
      >
        Quote
      </button>
      <button
        type="button"
        onClick={onPin}
        className="rounded px-3 py-1.5 text-sm text-gray-100 transition-all duration-150 hover:bg-purple-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
        aria-label="Pin selected text"
      >
        Pin
      </button>
      <button type="button" onClick={onDismiss} className="sr-only" aria-label="Dismiss text selection actions">
        Dismiss
      </button>
    </div>
  )
})

export default SelectionPopover
