import { useState } from 'react'

export interface DateRange {
  from: Date | null
  to: Date | null
  preset: string
}

interface DateFilterProps {
  onChange: (range: DateRange) => void
  defaultPreset?: string
}

const PRESETS = [
  { label: 'Last 1 hour', value: 'last_1h', hours: 1 },
  { label: 'Last 24 hours', value: 'last_24h', hours: 24 },
  { label: 'Last 7 days', value: 'last_7d', hours: 24 * 7 },
  { label: 'Last 30 days', value: 'last_30d', hours: 24 * 30 },
  { label: 'Custom', value: 'custom', hours: 0 },
]

/**
 * Date Filter Component
 *
 * Provides a date range picker with common presets and custom range support.
 * Propagates date changes to parent component for filtering panel data.
 */
export default function DateFilter({ onChange, defaultPreset = 'last_24h' }: DateFilterProps) {
  const [selectedPreset, setSelectedPreset] = useState(defaultPreset)
  const [customFrom, setCustomFrom] = useState('')
  const [customTo, setCustomTo] = useState('')
  const [showCustom, setShowCustom] = useState(false)

  const calculateDateRange = (presetValue: string): DateRange => {
    const preset = PRESETS.find(p => p.value === presetValue)
    if (!preset || preset.value === 'custom') {
      return {
        from: customFrom ? new Date(customFrom) : null,
        to: customTo ? new Date(customTo) : null,
        preset: 'custom',
      }
    }

    const to = new Date()
    const from = new Date(to.getTime() - preset.hours * 60 * 60 * 1000)

    return { from, to, preset: preset.value }
  }

  const handlePresetChange = (presetValue: string) => {
    setSelectedPreset(presetValue)
    setShowCustom(presetValue === 'custom')

    if (presetValue !== 'custom') {
      const range = calculateDateRange(presetValue)
      onChange(range)
    }
  }

  const handleCustomApply = () => {
    if (customFrom && customTo) {
      const range: DateRange = {
        from: new Date(customFrom),
        to: new Date(customTo),
        preset: 'custom',
      }
      onChange(range)
    }
  }

  // Format date to datetime-local input format (YYYY-MM-DDTHH:MM)
  const formatDateTimeLocal = (date: Date): string => {
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    return `${year}-${month}-${day}T${hours}:${minutes}`
  }

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        {/* Preset buttons */}
        <div className="flex flex-wrap gap-2">
          {PRESETS.map(preset => (
            <button
              key={preset.value}
              onClick={() => handlePresetChange(preset.value)}
              className={`
                px-3 py-1.5 text-sm font-medium rounded-md transition-colors
                ${
                  selectedPreset === preset.value
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }
              `}
            >
              {preset.label}
            </button>
          ))}
        </div>

        {/* Custom date inputs */}
        {showCustom && (
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 pt-2 sm:pt-0 border-t sm:border-t-0 sm:border-l border-gray-200 sm:pl-4">
            <div className="flex items-center gap-2">
              <label htmlFor="date-from" className="text-sm font-medium text-gray-700">
                From:
              </label>
              <input
                type="datetime-local"
                id="date-from"
                value={customFrom}
                onChange={e => setCustomFrom(e.target.value)}
                className="px-2 py-1 text-sm border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <div className="flex items-center gap-2">
              <label htmlFor="date-to" className="text-sm font-medium text-gray-700">
                To:
              </label>
              <input
                type="datetime-local"
                id="date-to"
                value={customTo}
                onChange={e => setCustomTo(e.target.value)}
                max={formatDateTimeLocal(new Date())}
                className="px-2 py-1 text-sm border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <button
              onClick={handleCustomApply}
              disabled={!customFrom || !customTo}
              className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
            >
              Apply
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
