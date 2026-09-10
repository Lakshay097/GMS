import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import './ExpirationWidget.css'

interface ExpirationSummary {
  total: number
  expiring_7d: number
  expiring_30d: number
  expired: number
  renewed: number
}

interface ExpirationRecord {
  id: string
  title: string
  entity_type: string
  expires_at: string
  status: string
  renew_by_at: string | null
  is_acknowledged: boolean
}

interface ExpirationWidgetProps {
  expanded: boolean
  onToggle: () => void
}

const ENTITY_LABELS: Record<string, string> = {
  certificate: 'Cert',
  license: 'Lic',
  lease: 'Lease',
  insurance: 'Ins',
  permit: 'Permit',
  calibration: 'Cal',
  training: 'Train',
  other: 'Other',
}

function daysUntil(dateStr: string): number {
  const now = new Date()
  const target = new Date(dateStr)
  return Math.ceil((target.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
}

function urgencyClass(expiresAt: string, status: string): string {
  if (status === 'expired') return 'urgency--critical'
  if (status === 'renewed') return 'urgency--renewed'
  const days = daysUntil(expiresAt)
  if (days <= 0) return 'urgency--critical'
  if (days <= 7) return 'urgency--critical'
  if (days <= 30) return 'urgency--warning'
  return 'urgency--ok'
}

function urgencyLabel(expiresAt: string, status: string): string {
  if (status === 'expired') return 'Expired'
  if (status === 'renewed') return 'Renewed'
  const days = daysUntil(expiresAt)
  if (days <= 0) return 'Expired today'
  if (days === 1) return 'Expires tomorrow'
  return `${days} days left`
}

export default function ExpirationWidget({ expanded, onToggle }: ExpirationWidgetProps) {
  const navigate = useNavigate()
  const [summary, setSummary] = useState<ExpirationSummary | null>(null)
  const [items, setItems] = useState<ExpirationRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'expiring' | 'expired'>('expiring')

  useEffect(() => {
    const controller = new AbortController()
    const load = async () => {
      try {
        setLoading(true)
        const [summaryRes, itemsRes] = await Promise.all([
          apiFetch('/api/v1/expiration-records/summary', { signal: controller.signal }),
          apiFetch('/api/v1/expiration-records/expiring-soon?days_ahead=90', { signal: controller.signal }),
        ])
        if (summaryRes.ok) setSummary(await summaryRes.json())
        if (itemsRes.ok) {
          const data = await itemsRes.json()
          setItems(Array.isArray(data) ? data : [])
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return
        // Silently fail — widget is optional
      } finally {
        setLoading(false)
      }
    }
    load()
    return () => controller.abort()
  }, [])

  const handleRenew = async (e: React.MouseEvent, recordId: string) => {
    e.stopPropagation()
    const newExpires = prompt('Enter new expiry date (YYYY-MM-DD):')
    if (!newExpires) return
    const expiresAt = new Date(newExpires)
    if (isNaN(expiresAt.getTime()) || expiresAt <= new Date()) {
      alert('Please enter a valid future date.')
      return
    }
    try {
      await apiFetch(`/api/v1/expiration-records/${recordId}/renew`, {
        method: 'POST',
        body: JSON.stringify({ new_expires_at: expiresAt.toISOString() }),
      })
      setItems(prev => prev.filter(i => i.id !== recordId))
      setSummary(prev => prev ? { ...prev, renewed: prev.renewed + 1, expired: Math.max(0, prev.expired - 1) } : prev)
    } catch {
      alert('Failed to renew. Please try again.')
    }
  }

  const handleAcknowledge = async (e: React.MouseEvent, recordId: string) => {
    e.stopPropagation()
    try {
      await apiFetch(`/api/v1/expiration-records/${recordId}/acknowledge`, { method: 'POST' })
      setItems(prev => prev.map(i => i.id === recordId ? { ...i, is_acknowledged: true } : i))
    } catch { /* ignore */ }
  }

  // No data — hide widget entirely
  if (!loading && !summary) return null

  const metaParts: string[] = []
  if (summary) {
    if (summary.expiring_7d > 0) metaParts.push(`${summary.expiring_7d} in 7d`)
    if (summary.expiring_30d > 0) metaParts.push(`${summary.expiring_30d} in 30d`)
    if (summary.expired > 0) metaParts.push(`${summary.expired} expired`)
  }
  const meta = metaParts.length > 0 ? metaParts.join(' · ') : summary ? 'All clear ✓' : undefined

  const expiringItems = items.filter(i => i.status === 'expiring_soon' || i.status === 'active')
  const expiredItems = items.filter(i => i.status === 'expired')
  const displayItems = activeTab === 'expiring' ? expiringItems : expiredItems

  return (
    <div className="dashboard-section">
      <button
        className="dashboard-section__header"
        aria-expanded={expanded}
        aria-controls="section-body-expiration"
        onClick={onToggle}
      >
        <span className="dashboard-section__chevron" aria-hidden="true">▶</span>
        <span className="dashboard-section__title">Expiration Reminders</span>
        {meta && <span className="dashboard-section__meta">{meta}</span>}
      </button>
      {expanded && (
        <div id="section-body-expiration" className="dashboard-section__body">
          {/* Summary ribbon */}
          {summary && (
            <div className="exp-summary-ribbon">
              <div className="exp-ribbon-item">
                <div className="exp-ribbon-num">{summary.total}</div>
                <div className="exp-ribbon-label">Total</div>
              </div>
              <div className="exp-ribbon-item exp-ribbon-item--warning">
                <div className="exp-ribbon-num">{summary.expiring_7d + summary.expiring_30d}</div>
                <div className="exp-ribbon-label">Expiring</div>
              </div>
              <div className="exp-ribbon-item exp-ribbon-item--critical">
                <div className="exp-ribbon-num">{summary.expired}</div>
                <div className="exp-ribbon-label">Expired</div>
              </div>
              <div className="exp-ribbon-item exp-ribbon-item--ok">
                <div className="exp-ribbon-num">{summary.renewed}</div>
                <div className="exp-ribbon-label">Renewed</div>
              </div>
            </div>
          )}

          {/* Tab bar */}
          <div className="exp-tabs">
            <button
              className={`exp-tab ${activeTab === 'expiring' ? 'exp-tab--active' : ''}`}
              onClick={() => setActiveTab('expiring')}
            >
              Expiring ({expiringItems.length})
            </button>
            <button
              className={`exp-tab ${activeTab === 'expired' ? 'exp-tab--active' : ''}`}
              onClick={() => setActiveTab('expired')}
            >
              Expired ({expiredItems.length})
            </button>
          </div>

          {/* Items list */}
          {loading ? (
            <div className="exp-loading">Loading…</div>
          ) : displayItems.length === 0 ? (
            <div className="exp-empty">
              {activeTab === 'expiring' ? 'No items expiring soon' : 'No expired items'}
            </div>
          ) : (
            <div className="exp-items">
              {displayItems.map(item => (
                <div
                  key={item.id}
                  className={`exp-item ${urgencyClass(item.expires_at, item.status)} ${item.is_acknowledged ? 'exp-item--acknowledged' : ''}`}
                  onClick={() => navigate(`/expiration-records/${item.id}`)}
                >
                  <div className="exp-item__icon">
                    <span style={{ fontSize: 'var(--text-micro)', fontWeight: 600, color: 'var(--ink-500)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{ENTITY_LABELS[item.entity_type] || 'Other'}</span>
                  </div>
                  <div className="exp-item__content">
                    <div className="exp-item__title">{item.title}</div>
                    <div className="exp-item__meta">
                      <span className="exp-item__type">{item.entity_type}</span>
                      <span className="exp-item__date">
                        Expires: {new Date(item.expires_at).toLocaleDateString()}
                      </span>
                      <span className={`exp-item__urgency ${urgencyClass(item.expires_at, item.status)}`}>
                        {urgencyLabel(item.expires_at, item.status)}
                      </span>
                    </div>
                    {item.renew_by_at && (
                      <div className="exp-item__renew-by">
                        Renew by: {new Date(item.renew_by_at).toLocaleDateString()}
                      </div>
                    )}
                  </div>
                  <div className="exp-item__actions">
                    {item.status === 'expired' && (
                      <button
                        className="exp-action-btn exp-action-btn--renew"
                        onClick={(e) => handleRenew(e, item.id)}
                        title="Mark as renewed"
                      >
                        Renew
                      </button>
                    )}
                    {!item.is_acknowledged && (
                      <button
                        className="exp-action-btn exp-action-btn--ack"
                        onClick={(e) => handleAcknowledge(e, item.id)}
                        title="Dismiss"
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Navigate to full list */}
          <div className="exp-footer">
            <button
              className="exp-footer-link"
              onClick={() => navigate('/expiration-records')}
            >
              View all expiration records →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
