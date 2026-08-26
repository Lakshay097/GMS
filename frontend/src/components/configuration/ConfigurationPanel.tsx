import { useState, useEffect } from 'react'
import { apiFetch } from '../../lib/api'

interface Configuration {
  [key: string]: any
}

export default function ConfigurationPanel() {
  const [globalConfig, setGlobalConfig] = useState<Configuration>({})
  const [schoolConfig, setSchoolConfig] = useState<Configuration>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'global' | 'school'>('global')
  const [selectedSchoolId, setSelectedSchoolId] = useState<string>('')

  useEffect(() => {
    const controller = new AbortController()
    fetchGlobalConfiguration(controller.signal)
    return () => controller.abort()
  }, [])

  const fetchGlobalConfiguration = async (signal?: AbortSignal) => {
    try {
      setLoading(true)
      const response = await apiFetch('/api/v1/configuration/global', { signal })
      
      if (!response.ok) {
        throw new Error('Failed to fetch global configuration')
      }
      
      const data = await response.json()
      setGlobalConfig(data.configuration)
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const fetchSchoolConfiguration = async (schoolId: string) => {
    try {
      setLoading(true)
      const response = await apiFetch(`/api/v1/configuration/schools/${schoolId}`)
      
      if (!response.ok) {
        throw new Error('Failed to fetch school configuration')
      }
      
      const data = await response.json()
      setSchoolConfig(data.configuration)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const [banner, setBanner] = useState<{ type: 'error' | 'success'; message: string } | null>(null)

  useEffect(() => {
    if (!banner) return
    const timer = setTimeout(() => setBanner(null), 5000)
    return () => clearTimeout(timer)
  }, [banner])

  const handleGlobalUpdate = async (updates: Configuration) => {
    try {
      const response = await apiFetch('/api/v1/configuration/global', {
        method: 'PATCH',
        body: JSON.stringify({ updates })
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error?.message || 'Failed to update configuration')
      }
      
      setBanner({ type: 'success', message: 'Configuration saved' })
      await fetchGlobalConfiguration()
    } catch (err) {
      setBanner({ type: 'error', message: err instanceof Error ? err.message : 'Failed to update configuration' })
    }
  }

  const handleSchoolUpdate = async (updates: Configuration) => {
    if (!selectedSchoolId) {
      setBanner({ type: 'error', message: 'Please select a school first' })
      return
    }

    try {
      const response = await apiFetch(`/api/v1/configuration/schools/${selectedSchoolId}`, {
        method: 'PATCH',
        body: JSON.stringify({ school_id: selectedSchoolId, updates })
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error?.message || 'Failed to update configuration')
      }
      
      setBanner({ type: 'success', message: 'Configuration saved' })
      await fetchSchoolConfiguration(selectedSchoolId)
    } catch (err) {
      setBanner({ type: 'error', message: err instanceof Error ? err.message : 'Failed to update configuration' })
    }
  }

  const handleConfigChange = (key: string, value: any, isGlobal: boolean) => {
    if (isGlobal) {
      setGlobalConfig(prev => ({ ...prev, [key]: value }))
    } else {
      setSchoolConfig(prev => ({ ...prev, [key]: value }))
    }
  }

  if (loading) return <div className="loading-state">Loading configuration…</div>
  if (error) return <div className="error">Error: {error}</div>

  return (
    <div className="configuration-panel page-shell">
      <div className="header">
        <h1>Configuration Management</h1>
      </div>

      {banner && (
        <div className={`alert alert-${banner.type}`}>
          <span className="alert-icon">{banner.type === 'error' ? '⚠️' : '✓'}</span>
          <span>{banner.message}</span>
          <button onClick={() => setBanner(null)} className="alert-close">×</button>
        </div>
      )}
      
      <div className="tabs">
        <button
          className={`tab ${activeTab === 'global' ? 'active' : ''}`}
          onClick={() => setActiveTab('global')}
        >
          Global Configuration
        </button>
        <button
          className={`tab ${activeTab === 'school' ? 'active' : ''}`}
          onClick={() => setActiveTab('school')}
        >
          School Configuration
        </button>
      </div>
      
      {activeTab === 'global' && (
        <div className="config-section">
          <h2>Global Configuration (SuperAdmin Only)</h2>
          <ConfigurationForm
            config={globalConfig}
            onChange={(key, value) => handleConfigChange(key, value, true)}
            onSave={() => handleGlobalUpdate(globalConfig)}
          />
        </div>
      )}
      
      {activeTab === 'school' && (
        <div className="config-section">
          <h2>School Configuration</h2>
          <div className="form-group">
            <label htmlFor="school_id">School ID</label>
            <input
              type="text"
              id="school_id"
              value={selectedSchoolId}
              onChange={(e) => setSelectedSchoolId(e.target.value)}
              placeholder="Enter school ID"
            />
            <button
              onClick={() => selectedSchoolId && fetchSchoolConfiguration(selectedSchoolId)}
              className="btn btn-sm"
            >
              Load Configuration
            </button>
          </div>
          
          {selectedSchoolId && (
            <ConfigurationForm
              config={schoolConfig}
              onChange={(key, value) => handleConfigChange(key, value, false)}
              onSave={() => handleSchoolUpdate(schoolConfig)}
            />
          )}
        </div>
      )}
    </div>
  )
}

function ConfigurationForm({
  config,
  onChange,
  onSave
}: {
  config: Configuration
  onChange: (key: string, value: any) => void
  onSave: () => void
}) {
  return (
    <div className="config-form">
      {Object.entries(config).map(([key, value], index) => (
        <div key={`config-${index}`} className="form-group">
          <label htmlFor={key}>{key}</label>
          {typeof value === 'boolean' ? (
            <input
              type="checkbox"
              id={key}
              checked={value}
              onChange={(e) => onChange(key, e.target.checked)}
            />
          ) : typeof value === 'number' ? (
            <input
              type="number"
              id={key}
              value={value}
              onChange={(e) => onChange(key, parseFloat(e.target.value))}
            />
          ) : typeof value === 'object' ? (
            <textarea
              id={key}
              value={JSON.stringify(value, null, 2)}
              onChange={(e) => {
                try {
                  onChange(key, JSON.parse(e.target.value))
                } catch {
                  // Invalid JSON, ignore
                }
              }}
              rows={5}
            />
          ) : (
            <input
              type="text"
              id={key}
              value={value}
              onChange={(e) => onChange(key, e.target.value)}
            />
          )}
        </div>
      ))}
      
      <button onClick={onSave} className="btn btn-primary">
        Save Configuration
      </button>
    </div>
  )
}