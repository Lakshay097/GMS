/**
 * Shared utility functions used across the application.
 * Centralizes date formatting, text helpers, and common patterns.
 */

/** Format an ISO date string to a human-readable short date (e.g., "Jan 26, 2026") */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  } catch {
    return iso
  }
}

/** Format an ISO datetime string to a short date + time (e.g., "Jan 26, 2026, 2:30 PM") */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

/** Format a state string like "under_investigation" to "Under Investigation" */
export function formatState(state: string): string {
  return state.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

/** Get initials from a name string (e.g., "John Doe" → "JD") */
export function getInitials(name?: string): string {
  if (!name) return '?'
  return name
    .split(' ')
    .filter(Boolean)
    .map(w => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

/** Check if a date string is overdue (past now) */
export function isOverdue(iso: string): boolean {
  return new Date(iso).getTime() < Date.now()
}

/** Check if a date string is due within the next N days (default: 3) */
export function isDueSoon(iso: string, days = 3): boolean {
  const diff = new Date(iso).getTime() - Date.now()
  const remaining = diff / (1000 * 60 * 60 * 24)
  return remaining <= days && remaining >= 0
}

/** Generic sort helper for arrays of objects */
export function sortItems<T>(items: T[], key: keyof T, dir: 'asc' | 'desc'): T[] {
  return [...items].sort((a, b) => {
    const av = a[key]
    const bv = b[key]
    if (av == null && bv == null) return 0
    if (av == null) return 1
    if (bv == null) return -1
    if (av < bv) return dir === 'asc' ? -1 : 1
    if (av > bv) return dir === 'asc' ? 1 : -1
    return 0
  })
}
