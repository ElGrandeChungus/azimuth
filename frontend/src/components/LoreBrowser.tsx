import { useEffect, useMemo, useState } from 'react'

import { getEntries, getEntry, searchEntries } from '../api/client'
import type { LoreEntry, LoreEntryListItem, LoreEntryType } from '../types'

interface LoreBrowserProps {
  isOpen: boolean
  onClose: () => void
}

const ENTRY_TYPES: LoreEntryType[] = ['location', 'faction', 'npc', 'event', 'culture']

function LoreBrowser({ isOpen, onClose }: LoreBrowserProps) {
  const [query, setQuery] = useState('')
  const [entries, setEntries] = useState<LoreEntryListItem[]>([])
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null)
  const [selectedEntry, setSelectedEntry] = useState<LoreEntry | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) {
      return
    }

    let cancelled = false

    const load = async () => {
      setIsLoading(true)
      try {
        const nextEntries = query.trim() ? await searchEntries(query.trim(), undefined, 50) : await getEntries()
        if (cancelled) return
        setEntries(nextEntries)
        if (!selectedSlug && nextEntries.length > 0) {
          setSelectedSlug(nextEntries[0].slug)
        }
        setError(null)
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load lore entries')
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false)
        }
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [isOpen, query, selectedSlug])

  useEffect(() => {
    if (!isOpen || !selectedSlug) {
      setSelectedEntry(null)
      return
    }

    let cancelled = false

    const loadDetail = async () => {
      try {
        const detail = await getEntry(selectedSlug)
        if (!cancelled) {
          setSelectedEntry(detail.entry)
          setError(null)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load entry details')
        }
      }
    }

    void loadDetail()
    return () => {
      cancelled = true
    }
  }, [isOpen, selectedSlug])

  const groupedEntries = useMemo(() => {
    const map: Record<string, LoreEntryListItem[]> = {
      location: [],
      faction: [],
      npc: [],
      event: [],
      culture: [],
    }

    for (const entry of entries) {
      const key = String(entry.type)
      if (!map[key]) {
        map[key] = []
      }
      map[key].push(entry)
    }

    for (const key of Object.keys(map)) {
      map[key].sort((a, b) => a.name.localeCompare(b.name))
    }

    return map
  }, [entries])

  const stats = useMemo(() => {
    const values: Record<string, number> = {}
    for (const type of ENTRY_TYPES) {
      values[type] = groupedEntries[type]?.length ?? 0
    }
    return values
  }, [groupedEntries])

  if (!isOpen) {
    return null
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4">
      <div className="flex h-[90vh] w-full max-w-6xl flex-col overflow-hidden rounded-lg border border-gray-700 bg-gray-900">
        <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3">
          <h2 className="text-sm font-semibold text-gray-100">Lore Browser</h2>
          <button type="button" onClick={onClose} className="text-sm text-gray-300 hover:text-white">
            Close
          </button>
        </div>

        <div className="flex items-center gap-3 border-b border-gray-800 px-4 py-3">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search lore..."
            className="w-full rounded-md border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-gray-100 focus:border-blue-500 focus:outline-none"
          />
          <div className="hidden text-xs text-gray-400 sm:block">{entries.length} results</div>
        </div>

        <div className="grid min-h-0 flex-1 grid-cols-1 md:grid-cols-[360px_1fr]">
          <div className="min-h-0 overflow-y-auto border-r border-gray-800 p-3">
            {error ? <p className="mb-3 rounded bg-red-950 px-3 py-2 text-xs text-red-200">{error}</p> : null}

            <div className="mb-3 grid grid-cols-2 gap-2">
              {ENTRY_TYPES.map((type) => (
                <div key={type} className="rounded border border-gray-800 bg-gray-950 px-2 py-2 text-xs text-gray-300">
                  <div className="font-semibold uppercase tracking-wide text-gray-400">{type}</div>
                  <div className="mt-1 text-sm text-gray-100">{stats[type]}</div>
                </div>
              ))}
            </div>

            {isLoading ? <p className="text-sm text-gray-400">Loading lore...</p> : null}

            {!isLoading && entries.length === 0 ? <p className="text-sm text-gray-400">No lore entries found.</p> : null}

            <div className="space-y-4">
              {ENTRY_TYPES.map((type) => {
                const group = groupedEntries[type] ?? []
                if (group.length === 0) {
                  return null
                }

                return (
                  <section key={type}>
                    <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">{type}</h3>
                    <ul className="space-y-1">
                      {group.map((entry) => (
                        <li key={entry.slug}>
                          <button
                            type="button"
                            onClick={() => setSelectedSlug(entry.slug)}
                            className={`w-full rounded border px-2 py-2 text-left text-sm transition ${
                              selectedSlug === entry.slug
                                ? 'border-blue-500 bg-blue-950/40 text-blue-100'
                                : 'border-gray-800 bg-gray-950 text-gray-200 hover:border-gray-700'
                            }`}
                          >
                            <div className="truncate font-medium">{entry.name}</div>
                            <div className="mt-1 text-xs text-gray-400">
                              {entry.category} • {entry.status}
                            </div>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </section>
                )
              })}
            </div>
          </div>

          <div className="min-h-0 overflow-y-auto p-4">
            {!selectedEntry ? (
              <p className="text-sm text-gray-400">Select an entry to view details.</p>
            ) : (
              <div className="space-y-4">
                <div>
                  <h3 className="text-lg font-semibold text-gray-100">{selectedEntry.name}</h3>
                  <p className="mt-1 text-xs uppercase tracking-wide text-gray-400">
                    {selectedEntry.type} • {selectedEntry.category} • {selectedEntry.status}
                  </p>
                </div>

                {selectedEntry.summary ? (
                  <p className="rounded border border-gray-800 bg-gray-950 px-3 py-2 text-sm text-gray-200">
                    {selectedEntry.summary}
                  </p>
                ) : null}

                {selectedEntry.metadata ? (
                  <div>
                    <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Fields</h4>
                    <pre className="overflow-x-auto rounded border border-gray-800 bg-gray-950 p-3 text-xs text-gray-200">
                      {JSON.stringify(selectedEntry.metadata, null, 2)}
                    </pre>
                  </div>
                ) : null}

                {selectedEntry.content ? (
                  <div>
                    <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Content</h4>
                    <pre className="whitespace-pre-wrap rounded border border-gray-800 bg-gray-950 p-3 text-sm text-gray-200">
                      {selectedEntry.content}
                    </pre>
                  </div>
                ) : null}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default LoreBrowser
