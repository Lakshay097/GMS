import { useState, useEffect } from 'react'
import { apiFetch } from '../../lib/api'

interface Setting {
  id: string
  key: string
  value: string
  description?: string
  category: string
  updated_at: string
}

export default function SettingsMasterData() {
  const [settings, setSettings] = useState<Setting[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [editingSetting, setEditingSetting] = useState<Setting | null>(null)
  
  const [formData, setFormData] = useState({
    key: '',
    value: '',
    description: '',
    category: 'general'
  })
  
  const [submitting, setSubmitting] = useState(false)
  const [activeTab, setActiveTab] = useState('settings')

  useEffect(() => {
    fetchSettings()
  }, [])

  const fetchSettings = async () => {
    try {
      setLoading(true)
      // Use the configuration API endpoint that exists in the backend
      const response = await apiFetch('/api/v1/configuration/global')
      if (response.ok) {
        const data = await response.json()
        // Convert configuration object to settings array format
        const settingsArray = Object.entries(data.configuration || {}).map(([key, value]) => ({
          id: key,
          key,
          value: String(value),
          description: '',
          category: 'general',
          updated_at: new Date().toISOString()
        }))
        setSettings(settingsArray)
      } else {
        setSettings([])
      }
    } catch (err) {
      console.error('Failed to fetch settings:', err)
      setSettings([])
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)

    try {
      // Use the configuration API endpoint
      const response = await apiFetch('/api/v1/configuration/global', {
        method: 'PATCH',
        body: JSON.stringify({
          updates: {
            [formData.key]: formData.value
          }
        })
      })

      if (!response.ok) {
        throw new Error('Failed to save setting')
      }

      await fetchSettings()
      setShowForm(false)
      setEditingSetting(null)
      setFormData({ key: '', value: '', description: '', category: 'general' })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setSubmitting(false)
    }
  }

  const handleEdit = (setting: Setting) => {
    setEditingSetting(setting)
    setFormData({
      key: setting.key,
      value: setting.value,
      description: setting.description || '',
      category: setting.category
    })
    setShowForm(true)
  }

  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null)

  const handleDelete = async (id: string) => {
    setPendingDeleteId(null)
    try {
      const response = await apiFetch('/api/v1/configuration/global', {
        method: 'PATCH',
        body: JSON.stringify({
          updates: {
            [id]: null
          }
        })
      })

      if (!response.ok) {
        throw new Error('Failed to delete setting')
      }

      await fetchSettings()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete setting')
    }
  }

  if (loading) return <div className="loading-state">Loading settings…</div>

  return (
    <div className="settings-master-data page-shell">
      <div className="header">
        <h1>Settings & Master Data</h1>
        <button 
          className="btn btn-primary" 
          onClick={() => {
            setEditingSetting(null)
            setFormData({ key: '', value: '', description: '', category: 'general' })
            setShowForm(!showForm)
          }}
        >
          {showForm ? 'Cancel' : 'Add Setting'}
        </button>
      </div>

      <div className="tabs">
        <button 
          className={`tab ${activeTab === 'settings' ? 'active' : ''}`}
          onClick={() => setActiveTab('settings')}
        >
          Settings
        </button>
        <button 
          className={`tab ${activeTab === 'master_data' ? 'active' : ''}`}
          onClick={() => setActiveTab('master_data')}
        >
          Master Data
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      {activeTab === 'settings' && (
        <>
          {showForm && (
            <form onSubmit={handleSubmit} className="config-form" style={{ marginBottom: '1.5rem' }}>
              <h3>{editingSetting ? 'Edit Setting' : 'Add New Setting'}</h3>
              
              <div className="form-group">
                <label htmlFor="key">Key *</label>
                <input
                  id="key"
                  type="text"
                  value={formData.key}
                  onChange={(e) => setFormData(prev => ({ ...prev, key: e.target.value }))}
                  required
                  disabled={!!editingSetting}
                />
              </div>

              <div className="form-group">
                <label htmlFor="value">Value *</label>
                <textarea
                  id="value"
                  value={formData.value}
                  onChange={(e) => setFormData(prev => ({ ...prev, value: e.target.value }))}
                  rows={3}
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="category">Category</label>
                <select
                  id="category"
                  value={formData.category}
                  onChange={(e) => setFormData(prev => ({ ...prev, category: e.target.value }))}
                >
                  <option value="general">General</option>
                  <option value="security">Security</option>
                  <option value="notifications">Notifications</option>
                  <option value="integrations">Integrations</option>
                  <option value="audit">Audit</option>
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="description">Description</label>
                <input
                  id="description"
                  type="text"
                  value={formData.description}
                  onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                />
              </div>

              <div className="form-actions">
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? 'Saving…' : (editingSetting ? 'Update' : 'Create')}
                </button>
                <button 
                  type="button" 
                  className="btn" 
                  onClick={() => {
                    setShowForm(false)
                    setEditingSetting(null)
                  }}
                >
                  Cancel
                </button>
              </div>
            </form>
          )}

          {settings.length === 0 ? (
            <div className="empty-state">No settings configured</div>
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Key</th>
                    <th>Value</th>
                    <th>Category</th>
                    <th>Description</th>
                    <th>Updated</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {settings.map((setting, index) => (
                    <tr key={`${setting.id}-${index}`}>
                      <td>
                        <code>{setting.key}</code>
                      </td>
                      <td>
                        <div style={{ 
                          maxWidth: '200px', 
                          overflow: 'hidden', 
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap'
                        }}>
                          {setting.value}
                        </div>
                      </td>
                      <td>
                        <span className="status status-active">
                          {setting.category}
                        </span>
                      </td>
                      <td>{setting.description || '-'}</td>
                      <td>{new Date(setting.updated_at).toLocaleDateString()}</td>
                      <td>
                        <button 
                          className="btn btn-sm"
                          onClick={() => handleEdit(setting)}
                        >
                          Edit
                        </button>
                        {pendingDeleteId === setting.id ? (
                          <span className="inline-confirm">
                            <span className="inline-confirm__text">Delete?</span>
                            <button className="btn btn-sm btn-danger" onClick={() => handleDelete(setting.id)}>Yes</button>
                            <button className="btn btn-sm btn-ghost" onClick={() => setPendingDeleteId(null)}>No</button>
                          </span>
                        ) : (
                          <button 
                            className="btn btn-sm btn-danger"
                            onClick={() => setPendingDeleteId(setting.id)}
                          >
                            Delete
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {activeTab === 'master_data' && (
        <div className="config-form">
          <h3>Master Data Management</h3>
          <p style={{ color: 'var(--text-muted)', marginBottom: '1rem' }}>
            Configure and manage master data entities such as categories, lookup values, and reference data.
          </p>
          
          <div className="info-banner">
            <strong>Note:</strong> Master data management features will be implemented based on your specific data requirements.
            This section can include management for:
          </div>
          
          <ul style={{ color: 'var(--text-muted)', paddingLeft: '1.5rem' }}>
            <li>KPI Categories</li>
            <li>Discrepancy Categories</li>
            <li>Role Definitions</li>
            <li>School Types</li>
            <li>Department Types</li>
            <li>Reference Data Tables</li>
          </ul>
        </div>
      )}
    </div>
  )
}