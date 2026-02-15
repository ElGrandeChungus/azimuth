interface PasteSourcePromptProps {
  isVisible: boolean
  label: string
  onLabelChange: (value: string) => void
  dontAskAgain: boolean
  onToggleDontAskAgain: (value: boolean) => void
  onApplyLabel: () => void
  onPastePlain: () => void
}

function PasteSourcePrompt({
  isVisible,
  label,
  onLabelChange,
  dontAskAgain,
  onToggleDontAskAgain,
  onApplyLabel,
  onPastePlain,
}: PasteSourcePromptProps) {
  if (!isVisible) {
    return null
  }

  return (
    <div className="mb-3 rounded-md border border-amber-700/60 bg-amber-950/60 px-3 py-2 text-xs text-amber-100">
      <p className="mb-2 font-medium">Large paste detected. Add a source label?</p>
      <div className="mb-2 flex flex-col gap-2 sm:flex-row sm:items-center">
        <input
          type="text"
          value={label}
          onChange={(event) => onLabelChange(event.target.value)}
          placeholder="e.g. Session notes, Rulebook p.42"
          className="w-full rounded border border-amber-700/70 bg-gray-950 px-2 py-1 text-xs text-gray-100 outline-none focus:border-blue-500"
        />
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onApplyLabel}
            disabled={!label.trim()}
            className="rounded bg-blue-600 px-2 py-1 text-xs font-semibold text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-gray-700"
          >
            Label Paste
          </button>
          <button
            type="button"
            onClick={onPastePlain}
            className="rounded border border-amber-700/70 px-2 py-1 text-xs text-amber-100 transition hover:bg-amber-900/70"
          >
            Paste As-Is
          </button>
        </div>
      </div>
      <label className="inline-flex items-center gap-2 text-xs text-amber-200">
        <input
          type="checkbox"
          checked={dontAskAgain}
          onChange={(event) => onToggleDontAskAgain(event.target.checked)}
        />
        Don't ask again
      </label>
    </div>
  )
}

export default PasteSourcePrompt
