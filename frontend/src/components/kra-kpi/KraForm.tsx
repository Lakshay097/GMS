import { useState, useEffect } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../../lib/api'

interface KraFormData {
  name: string
  description: string
}

export default function KraForm() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const isEdit = !!id

  const [form, setForm] = useState<KraFormData>({ name: '', description: '' })
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(isEdit)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isEdit) return
    const load = async () => {
      try {
        // We fetch the full list and find the one we need
        const res = await apiFetch('/api/v1/kras?include_deprecated=true')
        if (!res.ok) throw new Error('Failed to load KRA')
        const kras: { id: string; name: string; description: string | null }[] = await res.json()
        const kra = kras.find(k => k.id === id)
        if (!kra) throw new Error('KRA not found')
        setForm({ name: kra.name, description: kra.description ?? '' })
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load KRA')
      } finally {
        setFetching(false)
      }
    }
    load()
  }, [id, isEdit])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const payload = {
        name: form.name.trim(),
        description: form.description.trim() || null,
      }

      const res = isEdit
        ? await apiFetch(`/api/v1/kras/${id}`, {
            method: 'PATCH',
            body: JSON.stringify(payload),
          })
        : await apiFetch('/api/v1/kras', {
            method: 'POST',
            body: JSON.stringify(payload),
          })

      if (!res.ok) {
        const body = await res.json().catch(() => null)
        throw new Error(body?.error?.message || 'Save failed')
      }

      navigate('/kra')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setLoading(false)
    }
  }

  if (fetching) return <div className="loading-state">{t('common.loading')}</div>

  return (
    <div className="form-page page-shell">
      <div className="header">
        <h1>{isEdit ? t('kra.edit') : t('kra.new')}</h1>
        <Link to="/kra" className="btn btn-sm">{t('kra.back')}</Link>
      </div>

      {error && <div className="error">{error}</div>}

      <form onSubmit={handleSubmit} className="form-card">
        <div className="form-group">
          <label htmlFor="kra-name">{t('kra.name')} *</label>
          <input
            id="kra-name"
            type="text"
            value={form.name}
            onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            required
            minLength={1}
            maxLength={255}
            placeholder="e.g. Academic Performance"
            className="form-input"
          />
        </div>

        <div className="form-group">
          <label htmlFor="kra-desc">{t('kra.description')}</label>
          <textarea
            id="kra-desc"
            value={form.description}
            onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
            rows={3}
            maxLength={1000}
            placeholder="Optional description of this Key Result Area"
            className="form-input"
          />
        </div>

        <div className="form-actions">
          <Link to="/kra" className="btn btn-secondary">{t('kra.cancel')}</Link>
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? t('common.loading') : isEdit ? t('kra.update') : t('kra.create')}
          </button>
        </div>
      </form>
    </div>
  )
}
