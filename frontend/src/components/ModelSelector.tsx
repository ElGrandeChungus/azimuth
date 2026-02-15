import { useEffect, useState } from 'react'

import { getModels } from '../api/client'

interface ModelSelectorProps {
  value: string
  onChange: (model: string) => void
  disabled?: boolean
}

function ModelSelector({ value, onChange, disabled = false }: ModelSelectorProps) {
  const [models, setModels] = useState<Array<{ id: string; name: string }>>([])
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      setIsLoading(true)
      try {
        const modelOptions = await getModels()
        if (!cancelled) {
          setModels(modelOptions)
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
  }, [])

  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      disabled={disabled || isLoading}
      className="max-w-64 rounded-md border border-gray-700 bg-gray-900 px-3 py-1.5 text-xs text-gray-100 focus:border-blue-500 focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
    >
      <option value="">Default model</option>
      {models.map((model) => (
        <option key={model.id} value={model.id}>
          {model.name}
        </option>
      ))}
    </select>
  )
}

export default ModelSelector