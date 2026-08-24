import { useState, useEffect } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../../lib/api'

interface Kra {
  id: string
  name: string
  status: string
}

interface KpiFormData {
  kra_id: string
  title: string
  target_value: string
  comparator: string
  unit_of_measure: string
  frequency_code: string
  capture_type: string
  category_code: string
  is_sensitive: boolean
  amber_tolerance_band: string
}

const COMPARATORS = ['>=', '<=', '=', '>', '<']
const FREQUENCIES = ['daily', 'weekly', 'monthly', 'quarterly', 'annual', 'event']
const CAPTURE_TYPES = ['value_reading', 'checklist', 'percentage', 'count']

const DEFAULT_FORM: KpiFormData = {
  kra_id: '',
  title: '',
  target_value: '',
  comparator: '>=',
  unit_of_measure: '',
  frequency_code: 'monthly',
  capture_type: 'value_reading',
  category_code: '',
  is_sensitive: false,
  amber_tolerance_band: '',
}

export default function KpiForm() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  // Two entry-points: /kra/:kraId/kpi/new  OR  /kpi/:id/edit
  const { id: kpiId, kraId: kraIdParam } = useParams<{ id?: string; kraId?: string }>()
  const isEdit = !!kpiId

  const [form, setForm] = useState<KpiFormData>({ ...DEFAULT_FORM, kra_id: kraIdParam ?? '' })
  const [kras, setKras] = useState<Kra[]>([])
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(true)
  const [isImmutable, setIsImmutable] = useState(false)
  const [fieldPermissions, setFieldPermissions] = useState<Record<string, boolean>>({})
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        // Always load KRAs for the dropdown
        const kraRes = await apiFetch('/api/v1/kras?include_deprecated=false')
        if (kraRes.ok) {
          const data: Kra[] = await kraRes.json()
          setKras(data)
        }

        // Load field permissions for kpi_library module
        const permsRes = await apiFetch('/api/v1/permissions/fields?module=kpi_library')
        if (permsRes.ok) {
          const data = await permsRes.json()
          setFieldPermissions(data.permissions || {})
        }

        // If editing, load the KPI
        if (isEdit && kpiId) {
          const kpiRes = await apiFetch(`/api/v1/kpis/${kpiId}`)
          if (!kpiRes.ok) throw new Error('Failed to load KPI')
          const kpi = await kpiRes.json()
          setIsImmutable(kpi.is_immutable)
          setForm({
            kra_id: kpi.kra_id,
            title: kpi.title,
            target_value: String(kpi.target_value),
            comparator: kpi.comparator,
            unit_of_measure: kpi.unit_of_measure,
            frequency_code: kpi.frequency_code,
            capture_type: kpi.capture_type,
            category_code: kpi.category_code ?? '',
            is_sensitive: kpi.is_sensitive,
            amber_tolerance_band: kpi.amber_tolerance_band != null ? String(kpi.amber_tolerance_band) : '',
          })
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load data')
      } finally {
        setFetching(false)
      }
    }
    load()
  }, [isEdit, kpiId])

  const set = (field: keyof KpiFormData, value: string | boolean) =>
    setForm(f => ({ ...f, [field]: value }))

  const isFieldDisabled = (fieldName: string) => {
    return isImmutable || !fieldPermissions[fieldName]
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const payload: Record<string, unknown> = {
        title: form.title.trim(),
        target_value: parseFloat(form.target_value),
        comparator: form.comparator,
        unit_of_measure: form.unit_of_measure.trim(),
        frequency_code: form.frequency_code,
        capture_type: form.capture_type,
        is_sensitive: form.is_sensitive,
        ...(form.category_code.trim() && { category_code: form.category_code.trim() }),
        ...(form.amber_tolerance_band && { amber_tolerance_band: parseFloat(form.amber_tolerance_band) }),
      }

      let res: Response
      if (isEdit) {
        res = await apiFetch(`/api/v1/kpis/${kpiId}`, {
          method: 'PATCH',
          body: JSON.stringify(payload),
        })
      } else {
        res = await apiFetch('/api/v1/kpis', {
          method: 'POST',
          body: JSON.stringify({ ...payload, kra_id: form.kra_id }),
        })
      }

      if (!res.ok) {
        const body = await res.json().catch(() => null)
        throw new Error(body?.error?.message || 'Save failed')
      }

      // Go back to the KRA list (anchored to the right KRA)
      navigate('/kra')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setLoading(false)
    }
  }

  if (fetching) return <div className="loading-state">{t('common.loading')}</div>

  const backTo = kraIdParam ? `/kra` : '/kra'

  return (
    <div className="form-page page-shell">
      <div className="header">
        <h1>{isEdit ? t('kpi.edit') : t('kpi.new')}</h1>
        <Link to={backTo} className="btn btn-sm">{t('kpi.back')}</Link>
      </div>

      {isImmutable && (
        <div className="info-banner">
          🔒 {t('kpi.immutable')} — only non-structural fields can be changed.
        </div>
      )}

      {error && <div className="error">{error}</div>}

      <form onSubmit={handleSubmit} className="form-card">
        {/* KRA selector — only shown when creating */}
        {!isEdit && (
          <div className="form-group">
            <label htmlFor="kpi-kra">{t('kpi.kra')} *</label>
            <select
              id="kpi-kra"
              value={form.kra_id}
              onChange={e => set('kra_id', e.target.value)}
              required
              className="form-input"
            >
              <option value="">— select a KRA —</option>
              {kras.map((k, index) => (
                <option key={`kra-${index}`} value={k.id}>{k.name}</option>
              ))}
            </select>
          </div>
        )}

        <div className="form-group">
          <label htmlFor="kpi-title">{t('kpi.kpiTitle')} *</label>
          <input
            id="kpi-title"
            type="text"
            value={form.title}
            onChange={e => set('title', e.target.value)}
            required
            minLength={1}
            maxLength={255}
            placeholder="e.g. Attendance Rate"
            className="form-input"
            disabled={isImmutable}
          />
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="kpi-target">{t('kpi.targetValue')} *</label>
            <input
              id="kpi-target"
              type="number"
              step="any"
              value={form.target_value}
              onChange={e => set('target_value', e.target.value)}
              required
              placeholder="e.g. 95"
              className="form-input"
              disabled={isFieldDisabled('target_value')}
            />
          </div>

          <div className="form-group">
            <label htmlFor="kpi-comparator">{t('kpi.comparator')} *</label>
            <select
              id="kpi-comparator"
              value={form.comparator}
              onChange={e => set('comparator', e.target.value)}
              className="form-input"
              disabled={isFieldDisabled('comparator')}
            >
              {COMPARATORS.map((c, index) => (
                <option key={`comparator-${index}`} value={c}>{c}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="kpi-unit">{t('kpi.unit')} *</label>
            <input
              id="kpi-unit"
              type="text"
              value={form.unit_of_measure}
              onChange={e => set('unit_of_measure', e.target.value)}
              required
              maxLength={50}
              placeholder="e.g. %, count, hours"
              className="form-input"
              disabled={isImmutable}
            />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="kpi-freq">{t('kpi.frequency')} *</label>
            <select
              id="kpi-freq"
              value={form.frequency_code}
              onChange={e => set('frequency_code', e.target.value)}
              className="form-input"
              disabled={isImmutable}
            >
              {FREQUENCIES.map((f, index) => (
                <option key={`frequency-${index}`} value={f}>{f}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="kpi-capture">{t('kpi.captureType')} *</label>
            <select
              id="kpi-capture"
              value={form.capture_type}
              onChange={e => set('capture_type', e.target.value)}
              className="form-input"
              disabled={isImmutable}
            >
              {CAPTURE_TYPES.map((ct, index) => (
                <option key={`capture-type-${index}`} value={ct}>{ct}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="kpi-category">{t('kpi.category')}</label>
            <input
              id="kpi-category"
              type="text"
              value={form.category_code}
              onChange={e => set('category_code', e.target.value)}
              maxLength={50}
              placeholder="e.g. ACADEMIC"
              className="form-input"
              disabled={isFieldDisabled('category_code')}
            />
          </div>

          <div className="form-group">
            <label htmlFor="kpi-amber">{t('kpi.amberTolerance')}</label>
            <input
              id="kpi-amber"
              type="number"
              step="any"
              min="0"
              value={form.amber_tolerance_band}
              onChange={e => set('amber_tolerance_band', e.target.value)}
              placeholder="e.g. 5"
              className="form-input"
              disabled={isFieldDisabled('amber_tolerance_band')}
            />
          </div>
        </div>

        <div className="form-group form-group--inline">
          <label htmlFor="kpi-sensitive">
            <input
              id="kpi-sensitive"
              type="checkbox"
              checked={form.is_sensitive}
              onChange={e => set('is_sensitive', e.target.checked)}
              disabled={isFieldDisabled('is_sensitive')}
            />
            {' '}{t('kpi.isSensitive')}
          </label>
        </div>

        <div className="form-actions">
          <Link to={backTo} className="btn btn-secondary">{t('kpi.cancel')}</Link>
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? t('common.loading') : isEdit ? t('kpi.update') : t('kpi.create')}
          </button>
        </div>
      </form>
    </div>
  )
}
