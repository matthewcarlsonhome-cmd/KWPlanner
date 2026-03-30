import React, { useState, useEffect } from 'react'
import { settings as settingsApi } from '../lib/api'

export default function SettingsPage() {
  const [config, setConfig] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    settingsApi.get().then(setConfig).catch(console.error)
  }, [])

  const handleChange = (key, value) => {
    setConfig(prev => ({ ...prev, [key]: value }))
    setSaved(false)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const updated = await settingsApi.update(config)
      setConfig(updated)
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (err) {
      alert('Failed to save: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  if (!config) return <div className="text-gray-500 py-10 text-center">Loading settings...</div>

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Settings</h1>

      {/* Research Settings */}
      <section className="bg-white rounded-lg shadow-sm border p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Research Settings</h2>
        <div className="grid grid-cols-2 gap-4">
          {[
            { key: 'lookback_days', label: 'Lookback Days', type: 'number' },
            { key: 'min_seed_conversions', label: 'Min Seed Conversions', type: 'number', step: '0.1' },
            { key: 'min_seed_clicks', label: 'Min Seed Clicks', type: 'number' },
            { key: 'max_seeds_per_account', label: 'Max Seeds Per Account', type: 'number' },
            { key: 'min_monthly_searches', label: 'Min Monthly Searches', type: 'number' },
          ].map(field => (
            <div key={field.key}>
              <label className="block text-sm font-medium text-gray-700 mb-1">{field.label}</label>
              <input
                type={field.type}
                step={field.step}
                value={config[field.key] ?? ''}
                onChange={e => handleChange(field.key, field.type === 'number' ? Number(e.target.value) : e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
              />
            </div>
          ))}
        </div>
      </section>

      {/* Priority Thresholds */}
      <section className="bg-white rounded-lg shadow-sm border p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Priority Thresholds</h2>
        <div className="grid grid-cols-3 gap-4">
          {[
            { key: 'high_priority_threshold', label: 'HIGH (>=)', color: 'green' },
            { key: 'medium_priority_threshold', label: 'MEDIUM (>=)', color: 'yellow' },
            { key: 'low_priority_threshold', label: 'LOW (>=)', color: 'gray' },
          ].map(field => (
            <div key={field.key}>
              <label className="block text-sm font-medium text-gray-700 mb-1">{field.label}</label>
              <input
                type="number"
                value={config[field.key] ?? ''}
                onChange={e => handleChange(field.key, Number(e.target.value))}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
              />
            </div>
          ))}
        </div>
      </section>

      {/* Scoring Weights */}
      <section className="bg-white rounded-lg shadow-sm border p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Scoring Weights</h2>
        <p className="text-sm text-gray-500 mb-3">Weights must sum to 100.</p>
        <div className="grid grid-cols-2 gap-4">
          {[
            { key: 'volume_weight', label: 'Volume Weight' },
            { key: 'competition_weight', label: 'Competition Weight' },
            { key: 'cpc_weight', label: 'CPC Efficiency Weight' },
            { key: 'relevance_weight', label: 'Relevance Weight' },
          ].map(field => (
            <div key={field.key}>
              <label className="block text-sm font-medium text-gray-700 mb-1">{field.label}</label>
              <input
                type="number"
                value={config[field.key] ?? ''}
                onChange={e => handleChange(field.key, Number(e.target.value))}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
              />
            </div>
          ))}
        </div>
        <p className="text-sm text-gray-400 mt-2">
          Current sum: {(config.volume_weight || 0) + (config.competition_weight || 0) + (config.cpc_weight || 0) + (config.relevance_weight || 0)}
        </p>
      </section>

      {/* API Configuration */}
      <section className="bg-white rounded-lg shadow-sm border p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">API Configuration</h2>
        <div className="space-y-3 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-500">Developer Token</span>
            <span className="font-mono text-gray-700">****configured via .env****</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">OAuth2 Status</span>
            <span className="text-green-600">Connected (Dev Mode)</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">MCC Account ID</span>
            <span className="font-mono text-gray-700">configured via .env</span>
          </div>
          <p className="text-xs text-gray-400 mt-2">
            API credentials are managed through environment variables (.env file).
            See the deployment guide for setup instructions.
          </p>
        </div>
      </section>

      {/* Save */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save Settings'}
        </button>
        {saved && <span className="text-green-600 text-sm">Settings saved!</span>}
      </div>
    </div>
  )
}
