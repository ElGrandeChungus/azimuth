import { useEffect, useMemo, useState } from 'react'

import {
  createSystemPrompt,
  deleteSystemPrompt,
  getModels,
  getSettings,
  getSystemPrompts,
  updateSettings,
  updateSystemPrompt,
} from '../api/client'
import type { SystemPrompt } from '../types'

interface SettingsPanelProps {
  isOpen: boolean
  onClose: () => void
}

type PromptUpdates = {
  name?: string
  content?: string
  is_default?: boolean
}

function SettingsPanel({ isOpen, onClose }: SettingsPanelProps) {
  const [apiKey, setApiKey] = useState('')
  const [defaultModel, setDefaultModel] = useState('')
  const [models, setModels] = useState<Array<{ id: string; name: string }>>([])
  const [prompts, setPrompts] = useState<SystemPrompt[]>([])
  const [newPromptName, setNewPromptName] = useState('')
  const [newPromptContent, setNewPromptContent] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const sortedPrompts = useMemo(
    () => [...prompts].sort((a, b) => Number(b.is_default) - Number(a.is_default) || a.name.localeCompare(b.name)),
    [prompts],
  )

  useEffect(() => {
    if (!isOpen) {
      return
    }

    let cancelled = false

    const load = async () => {
      try {
        const [settings, modelOptions, promptOptions] = await Promise.all([
          getSettings(),
          getModels(),
          getSystemPrompts(),
        ])

        if (cancelled) {
          return
        }

        setApiKey(String(settings.openrouter_api_key ?? ''))
        setDefaultModel(String(settings.default_model ?? ''))
        setModels(modelOptions)
        setPrompts(promptOptions)
        setError(null)
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load settings')
        }
      }
    }

    void load()

    return () => {
      cancelled = true
    }
  }, [isOpen])

  if (!isOpen) {
    return null
  }

  const saveSettings = async () => {
    setIsSaving(true)
    try {
      await updateSettings({
        openrouter_api_key: apiKey,
        default_model: defaultModel,
      })
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save settings')
    } finally {
      setIsSaving(false)
    }
  }

  const createPrompt = async () => {
    if (!newPromptName.trim() || !newPromptContent.trim()) {
      return
    }

    try {
      const prompt = await createSystemPrompt(newPromptName.trim(), newPromptContent.trim())
      setPrompts((current) => [...current, prompt])
      setNewPromptName('')
      setNewPromptContent('')
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create prompt')
    }
  }

  const handlePromptChange = async (promptId: string, updates: PromptUpdates) => {
    try {
      const updated = await updateSystemPrompt(promptId, updates)
      setPrompts((current) => {
        if (updates.is_default) {
          return current.map((item) =>
            item.id === promptId ? { ...updated, is_default: true } : { ...item, is_default: false },
          )
        }

        return current.map((item) => (item.id === promptId ? updated : item))
      })
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update prompt')
    }
  }

  const handleDeletePrompt = async (prompt: SystemPrompt) => {
    try {
      await deleteSystemPrompt(prompt.id)
      setPrompts((current) => current.filter((item) => item.id !== prompt.id))
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete prompt')
    }
  }

  const getPrompt = (promptId: string): SystemPrompt | undefined => prompts.find((item) => item.id === promptId)

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4">
      <div className="flex h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-lg border border-gray-700 bg-gray-900">
        <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3">
          <h2 className="text-sm font-semibold text-gray-100">Settings</h2>
          <button type="button" onClick={onClose} className="text-sm text-gray-300 hover:text-white">
            Close
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {error ? <p className="mb-4 rounded bg-red-950 px-3 py-2 text-sm text-red-200">{error}</p> : null}

          <section className="mb-6 space-y-3">
            <h3 className="text-sm font-semibold text-gray-100">OpenRouter</h3>
            <input
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder="OpenRouter API key"
              className="w-full rounded-md border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-gray-100 focus:border-blue-500 focus:outline-none"
            />
            <select
              value={defaultModel}
              onChange={(event) => setDefaultModel(event.target.value)}
              className="w-full rounded-md border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-gray-100 focus:border-blue-500 focus:outline-none"
            >
              <option value="">Select default model</option>
              {models.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => {
                void saveSettings()
              }}
              disabled={isSaving}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500 disabled:opacity-60"
            >
              {isSaving ? 'Saving...' : 'Save Settings'}
            </button>
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-semibold text-gray-100">System Prompts</h3>

            <div className="space-y-2 rounded-md border border-gray-800 bg-gray-950 p-3">
              <input
                value={newPromptName}
                onChange={(event) => setNewPromptName(event.target.value)}
                placeholder="Prompt name"
                className="w-full rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-100 focus:border-blue-500 focus:outline-none"
              />
              <textarea
                value={newPromptContent}
                onChange={(event) => setNewPromptContent(event.target.value)}
                rows={3}
                placeholder="Prompt content"
                className="w-full rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-100 focus:border-blue-500 focus:outline-none"
              />
              <button
                type="button"
                onClick={() => {
                  void createPrompt()
                }}
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500"
              >
                Add Prompt
              </button>
            </div>

            <div className="space-y-3">
              {sortedPrompts.map((prompt) => (
                <div key={prompt.id} className="rounded-md border border-gray-800 bg-gray-950 p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <input
                      value={prompt.name}
                      onChange={(event) => {
                        const name = event.target.value
                        setPrompts((current) =>
                          current.map((item) => (item.id === prompt.id ? { ...item, name } : item)),
                        )
                      }}
                      onBlur={() => {
                        const current = getPrompt(prompt.id)
                        if (current) {
                          void handlePromptChange(prompt.id, { name: current.name })
                        }
                      }}
                      className="w-full rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-100 focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                  <textarea
                    value={prompt.content}
                    onChange={(event) => {
                      const content = event.target.value
                      setPrompts((current) =>
                        current.map((item) => (item.id === prompt.id ? { ...item, content } : item)),
                      )
                    }}
                    onBlur={() => {
                      const current = getPrompt(prompt.id)
                      if (current) {
                        void handlePromptChange(prompt.id, { content: current.content })
                      }
                    }}
                    rows={4}
                    className="mb-2 w-full rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-100 focus:border-blue-500 focus:outline-none"
                  />

                  <div className="flex items-center justify-between">
                    <label className="flex items-center gap-2 text-xs text-gray-300">
                      <input
                        type="checkbox"
                        checked={prompt.is_default}
                        onChange={(event) => {
                          const isDefault = event.target.checked
                          if (isDefault) {
                            void handlePromptChange(prompt.id, { is_default: true })
                          }
                        }}
                      />
                      Default
                    </label>

                    <button
                      type="button"
                      onClick={() => {
                        void handleDeletePrompt(prompt)
                      }}
                      disabled={prompt.is_default}
                      className="rounded-md border border-red-700 px-3 py-1 text-xs text-red-300 hover:bg-red-950 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}

export default SettingsPanel