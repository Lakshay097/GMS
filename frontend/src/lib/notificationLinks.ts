/**
 * Notification deep-links — map a notification's entity_type/entity_id
 * (already stored on each notifications row) to the SPA route that shows
 * the entity. Returns null when the entity has no detail route or the
 * current user's roles cannot open it, so the bell never links to a
 * permission dead-end.
 */
export interface NotificationEntityRef {
  entity_type: string | null
  entity_id: string | null
}

const ADMIN_TYPES = new Set(['school', 'department', 'user', 'configuration'])

/** entity_type → path builder. Absent = no detail route exists. */
const LINKS: Record<string, (id: string) => string> = {
  task: (id) => `/tasks/${id}`,
  discrepancy: (id) => `/discrepancies/${id}`,
  observation: () => '/observations', // list — no observation detail route
  kpi: (id) => `/kpi/${id}/edit`,
  school: (id) => `/schools/${id}/edit`,
  department: (id) => `/departments/${id}/edit`,
  user: (id) => `/users/${id}/edit`,
}

/**
 * Route for a notification's entity, or null when not linkable:
 * unknown type, missing id, or an admin-only entity for a non-admin.
 */
export function notificationLink(
  ref: NotificationEntityRef,
  roles: string[],
): string | null {
  const type = ref.entity_type?.toLowerCase()
  const id = ref.entity_id
  if (!type || !id) return null
  if (ADMIN_TYPES.has(type)) {
    const isAdmin = roles.some((r) => ['superadmin', 'admin'].includes(r.toLowerCase()))
    if (!isAdmin) return null
  }
  return LINKS[type]?.(id) ?? null
}
