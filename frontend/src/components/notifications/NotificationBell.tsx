import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthContext } from '../../contexts/AuthContext'
import { notificationLink } from '../../lib/notificationLinks'
import { useCloseOnRouteChange, useDismiss } from '../../hooks/useCloseOnRouteChange'

interface Notification {
  id: string
  title: string
  body: string
  created_at: string
  read_at: string | null
  entity_type: string | null
  entity_id: string | null
}

/**
 * Bell icon + dropdown listing MY in-app notifications.
 * Read state is per-user server-side (`read_at`); the badge shows unread count.
 * Items whose entity has a route deep-link to it (task, discrepancy, KPI entry…);
 * clicking always marks the item read.
 */
/** `onOpen` fires when the dropdown opens — other chrome surfaces close themselves. */
export default function NotificationBell({ onOpen }: { onOpen?: () => void }) {
  const navigate = useNavigate()
  const { roles } = useAuthContext()
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<Notification[]>([])
  const [unread, setUnread] = useState(0)
  const [loading, setLoading] = useState(false)
  const wrapperRef = useRef<HTMLDivElement>(null)

  const close = useCallback(() => setOpen(false), [])
  useCloseOnRouteChange(open, close)
  const dismissHandlers = useDismiss(wrapperRef, open, close)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/v1/notifications?page=1&page_size=20', { credentials: 'include' })
      if (res.ok) {
        const data = await res.json()
        setItems(data.data)
        setUnread(data.unread_count)
      }
    } finally {
      setLoading(false)
    }
  }, [])

  // Badge count stays fresh while the dropdown is closed
  useEffect(() => {
    let cancelled = false
    const tick = async () => {
      try {
        const res = await fetch('/api/v1/notifications/unread-count', { credentials: 'include' })
        if (res.ok && !cancelled) setUnread((await res.json()).unread_count)
      } catch { /* offline — retry next tick */ }
    }
    tick()
    const timer = setInterval(tick, 30_000)
    return () => { cancelled = true; clearInterval(timer) }
  }, [])

  // Route change closes the dropdown (deep-link navigations included).
  // Render-time state adjustment per https://react.dev/learn/you-might-not-need-an-effect.

  const toggle = () => {
    const next = !open
    setOpen(next)
    if (next) { onOpen?.(); load() }
  }

  const markAll = async () => {
    await fetch('/api/v1/notifications/read-all', { method: 'POST', credentials: 'include' }).catch(() => undefined)
    setItems(prev => prev.map(n => ({ ...n, read_at: n.read_at || new Date().toISOString() })))
    setUnread(0)
  }

  const markOne = async (id: string) => {
    await fetch(`/api/v1/notifications/${id}/read`, { method: 'POST', credentials: 'include' }).catch(() => undefined)
    setItems(prev => prev.map(n => (n.id === id ? { ...n, read_at: new Date().toISOString() } : n)))
    setUnread(u => Math.max(0, u - 1))
  }

  /** Click behaviour: deep-link when the entity has a route, always mark read. */
  const openItem = (n: Notification) => {
    if (!n.read_at) markOne(n.id)
    const link = notificationLink(n, roles)
    if (link) {
      close()
      navigate(link)
    }
  }

  return (
    <div className="notif-wrapper" ref={wrapperRef} {...dismissHandlers}>
      <button className="notif-bell" onClick={toggle} aria-label="Notifications" aria-expanded={open}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
        {unread > 0 && <span className="notif-bell__badge">{unread > 99 ? '99+' : unread}</span>}
      </button>

      {open && (
        <div className="notif-dropdown" role="dialog" aria-label="Notifications">
          <div className="notif-dropdown__header">
            <span>Notifications</span>
            {unread > 0 && (
              <button className="notif-dropdown__markall" onClick={markAll}>Mark all read</button>
            )}
          </div>
          <div className="notif-dropdown__list">
            {loading && items.length === 0 && <div className="notif-dropdown__empty">Loading…</div>}
            {!loading && items.length === 0 && (
              <div className="notif-dropdown__empty">No notifications yet</div>
            )}
            {items.map(n => {
              const link = notificationLink(n, roles)
              return (
                <div
                  key={n.id}
                  className={`notif-item ${n.read_at ? 'notif-item--read' : 'notif-item--unread'} ${link ? 'notif-item--linked' : ''}`}
                  role={link ? 'link' : undefined}
                  tabIndex={link ? 0 : undefined}
                  onClick={() => openItem(n)}
                  onKeyDown={(e) => { if (link && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); openItem(n) } }}
                  title={link ? 'Open' : n.read_at ? undefined : 'Mark as read'}
                >
                  <div className="notif-item__title">
                    {!n.read_at && <span className="notif-item__dot" aria-hidden="true" />}
                    {n.title}
                    {link && <span className="notif-item__go" aria-hidden="true">→</span>}
                  </div>
                  <div className="notif-item__body">{n.body}</div>
                  <div className="notif-item__time">{new Date(n.created_at).toLocaleString()}</div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
