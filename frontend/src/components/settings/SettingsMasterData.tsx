import React, { useState, useEffect, useCallback } from 'react'
import { apiFetch } from '../../lib/api'
import { useSchoolContext } from '../../contexts/SchoolContext'
import { useAuthContext } from '../../contexts/AuthContext'
import { formatDate } from '../../lib/utils'

/* ─── Types ─────────────────────────────────────────────────────── */

interface ConfigItem {
  config_key: string
  value_type: string
  global_default: string
  editable_by: string
  overridable_scope: string
  current_value: string | null
  school_override: string | null
}

interface Holiday {
  id: string
  school_id: string | null
  holiday_date: string
  label: string
  recurrence_type: string
  created_by: string | null
  created_at: string
}

interface Asset {
  id: string
  school_id: string
  name: string
  category_code: string | null
  location_id: string | null
  status: string
  created_at: string
  updated_at: string
}

interface DiscrepancyCategory {
  id: string
  name: string
  status: string
  allow_delegate: boolean
  created_at: string
}

interface Location {
  id: string
  school_id: string
  name: string
  location_type: string
  status: string
  created_at: string
  updated_at: string
}

interface FeatureFlag {
  flag_key: string
  enabled: boolean
  description: string | null
  updated_at: string
}

interface ApprovalLevel {
  level: number
  role_id?: string
  user_id?: string
  assignee_type: 'role' | 'user'
  auto_escalation_sla_hours?: number
}

interface ApprovalChain {
  chain_version_id: string
  name: string
  description?: string
  levels: ApprovalLevel[]
  is_active: boolean
  priority: number
  category_id?: string
  created_at: string
}

/* ─── Friendly labels for config keys ───────────────────────────── */

/* ─── Grouped settings dashboard config ────────────────────────── */

type ControlType = 'number' | 'select' | 'readonly'

interface SettingItem {
  key: string
  label: string
  description: string
  control: ControlType
  min?: number
  max?: number
  step?: number
  unit?: string
  options?: { value: string; label: string }[]
  readOnly?: boolean
}

interface SettingGroup {
  id: string
  label: string
  icon: string
  description: string
  items: SettingItem[]
}

const SETTING_GROUPS: SettingGroup[] = [
  {
    id: 'scheduling',
    label: 'Scheduling',
    icon: '🕐',
    description: 'Observation timing, detection windows, and review cadence',
    items: [
      { key: 'observation_lock_period_minutes', label: 'Observation Lock Period', description: 'Minutes after submission before an observation is locked', control: 'number', min: 5, max: 1440, step: 5, unit: 'min' },
      { key: 'duplicate_detection_window_minutes', label: 'Duplicate Detection Window', description: 'Minutes within which duplicate observations are flagged', control: 'number', min: 5, max: 480, step: 5, unit: 'min' },
      { key: 'grace_period_hours', label: 'Grace Period', description: 'Hours after deadline before marking as missed', control: 'number', min: 1, max: 168, step: 1, unit: 'hrs' },
      { key: 'reminder_frequency_hours', label: 'Reminder Frequency', description: 'Hours between reminder notifications', control: 'number', min: 1, max: 168, step: 1, unit: 'hrs' },
      { key: 'performance_review_cadence_days', label: 'Review Cadence', description: 'Days between performance review cycles', control: 'number', min: 7, max: 365, step: 7, unit: 'days' },
      { key: 'max_eta_extensions', label: 'Max ETA Extensions', description: 'Maximum number of ETA extension requests per task', control: 'readonly', readOnly: true },
    ],
  },
  {
    id: 'escalation',
    label: 'Escalation & Tasks',
    icon: '⚡',
    description: 'SLA timers for escalation levels and task reminders',
    items: [
      { key: 'escalation_sla_level_1_hours', label: 'Escalation SLA — Level 1', description: 'Hours before level-1 escalation fires', control: 'number', min: 1, max: 720, step: 1, unit: 'hrs' },
      { key: 'escalation_sla_level_2_hours', label: 'Escalation SLA — Level 2', description: 'Hours before level-2 escalation fires', control: 'number', min: 1, max: 720, step: 1, unit: 'hrs' },
      { key: 'escalation_sla_level_3_hours', label: 'Escalation SLA — Level 3', description: 'Hours before level-3 escalation fires', control: 'number', min: 1, max: 720, step: 1, unit: 'hrs' },
      { key: 'task_escalation_level_1_sla_hours', label: 'Task Escalation — Level 1', description: 'Hours before task level-1 escalation', control: 'number', min: 1, max: 720, step: 1, unit: 'hrs' },
      { key: 'task_escalation_level_2_sla_hours', label: 'Task Escalation — Level 2', description: 'Hours before task level-2 escalation', control: 'number', min: 1, max: 720, step: 1, unit: 'hrs' },
      { key: 'task_escalation_level_3_sla_hours', label: 'Task Escalation — Level 3', description: 'Hours before task level-3 escalation', control: 'number', min: 1, max: 720, step: 1, unit: 'hrs' },
      { key: 'task_reminder_hours_before_eta', label: 'Task Reminder', description: 'Hours before ETA to send task reminder', control: 'number', min: 1, max: 168, step: 1, unit: 'hrs' },
    ],
  },
  {
    id: 'kpi',
    label: 'KPI Scoring',
    icon: '📊',
    description: 'Rounding, tolerance, and missing-data behaviour for KPI values',
    items: [
      { key: 'kpi_amber_tolerance_band', label: 'Amber Tolerance Band', description: 'Tolerance band for amber status threshold', control: 'number', min: 0, max: 50, step: 0.5, unit: '%' },
      { key: 'kpi_rounding_decimal_places', label: 'Rounding Decimal Places', description: 'Decimal places for KPI value rounding', control: 'number', min: 0, max: 6, step: 1, unit: 'dp' },
      { key: 'kpi_rounding_mode', label: 'Rounding Mode', description: 'Rounding strategy for KPI values', control: 'select', options: [
        { value: 'round_half_up', label: 'Round Half Up' },
        { value: 'round_half_down', label: 'Round Half Down' },
        { value: 'round_half_even', label: 'Round Half Even (Banker)' },
        { value: 'floor', label: 'Floor (Always Down)' },
        { value: 'ceil', label: 'Ceil (Always Up)' },
      ]},
      { key: 'kpi_missing_data_behavior', label: 'Missing Data Behaviour', description: 'How to handle missing KPI data submissions', control: 'select', options: [
        { value: 'not_submitted', label: 'Mark as Not Submitted' },
        { value: 'zero', label: 'Treat as Zero' },
        { value: 'carry_forward', label: 'Carry Forward Last Value' },
      ]},
    ],
  },
  {
    id: 'security',
    label: 'Security & Session',
    icon: '🔒',
    description: 'Session timeout, upload limits, and language support',
    items: [
      { key: 'session_timeout_minutes', label: 'Session Timeout', description: 'Minutes of inactivity before session expires', control: 'number', min: 5, max: 480, step: 5, unit: 'min' },
      { key: 'file_upload_max_size_mb', label: 'Max Upload Size', description: 'Maximum file upload size in MB', control: 'number', min: 1, max: 100, step: 1, unit: 'MB' },
    ],
  },
  {
    id: 'archive',
    label: 'Archive & Retention',
    icon: '🗄️',
    description: 'Data lifecycle tiers and evidence retention periods',
    items: [
      { key: 'evidence_retention_period_days', label: 'Evidence Retention', description: 'Days to retain evidence files before archival', control: 'number', min: 30, max: 3650, step: 30, unit: 'days' },
      { key: 'archive_hot_to_warm_days', label: 'Hot → Warm Tier', description: 'Days before data moves from hot to warm tier', control: 'number', min: 7, max: 365, step: 7, unit: 'days' },
      { key: 'archive_warm_to_cold_days', label: 'Warm → Cold Tier', description: 'Days before data moves from warm to cold tier', control: 'number', min: 30, max: 1825, step: 30, unit: 'days' },
      { key: 'archive_retention_years', label: 'Total Retention', description: 'Years to retain archived data before deletion', control: 'number', min: 1, max: 20, step: 1, unit: 'yrs' },
    ],
  },
]

const WORKING_DAY_OPTIONS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']

/* ─── Component ─────────────────────────────────────────────────── */

export default function SettingsMasterData() {
  const { activeSchoolId } = useSchoolContext()
  const { roles } = useAuthContext()
  const isSuperAdmin = roles.some(r => r.toLowerCase() === 'superadmin')
  const isAdmin = roles.some(r => r.toLowerCase() === 'admin')

  const [activeTab, setActiveTab] = useState<'settings' | 'master_data' | 'feature_flags'>('settings')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [banner, setBanner] = useState<{ type: 'error' | 'success'; message: string } | null>(null)

  // Auto-dismiss banner (success: 3s, error: 5s)
  useEffect(() => {
    if (!banner) return
    const ms = banner.type === 'error' ? 5000 : 3000
    const timer = setTimeout(() => setBanner(null), ms)
    return () => clearTimeout(timer)
  }, [banner])

  // ─── Settings state ────────────────────────────────────────────
  const [configItems, setConfigItems] = useState<ConfigItem[]>([])
  const [savingKey, setSavingKey] = useState<string | null>(null)
  const [confirmAction, setConfirmAction] = useState<{ label: string; onConfirm: () => void } | null>(null)

  // ─── Feature Flags state ───────────────────────────────────────
  const [featureFlags, setFeatureFlags] = useState<FeatureFlag[]>([])

  const fetchConfig = useCallback(async () => {
    try {
      setLoading(true)
      const res = await apiFetch('/api/v1/settings/configuration/')
      if (res.ok) {
        const data = await res.json()
        setConfigItems(Array.isArray(data) ? data : [])
      } else {
        setConfigItems([])
      }
    } catch {
      setConfigItems([])
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchFeatureFlags = useCallback(async () => {
    try {
      const res = await apiFetch('/api/v1/feature-flags/')
      if (res.ok) setFeatureFlags(await res.json())
    } catch { /* ignore */ }
  }, [])

  const handleToggleFlag = async (flagKey: string, currentEnabled: boolean) => {
    if (!isSuperAdmin) return
    try {
      const res = await apiFetch(`/api/v1/feature-flags/${flagKey}`, {
        method: 'PATCH',
        body: JSON.stringify({ enabled: !currentEnabled }),
      })
      if (res.ok) {
        setBanner({ type: 'success', message: `${flagKey} ${!currentEnabled ? 'enabled' : 'disabled'}` })
        fetchFeatureFlags()
      } else {
        const err = await res.json().catch(() => null)
        setBanner({ type: 'error', message: err?.detail || 'Failed to toggle flag' })
      }
    } catch {
      setBanner({ type: 'error', message: 'Network error' })
    }
  }

  // ─── Master Data state ─────────────────────────────────────────
  const [masterTab, setMasterTab] = useState<'holidays' | 'working_days' | 'locations' | 'assets' | 'discrepancy_categories'>('holidays')

  // Holidays
  const [holidays, setHolidays] = useState<Holiday[]>([])
  const [holidayForm, setHolidayForm] = useState({ holiday_date: '', label: '', recurrence_type: 'one_time' })
  const [showHolidayForm, setShowHolidayForm] = useState(false)

  // Working Days
  const [workingDays, setWorkingDays] = useState<string[]>([])

  // Assets
  const [assets, setAssets] = useState<Asset[]>([])
  const [assetForm, setAssetForm] = useState({ name: '', category_code: '', location_id: '' })
  const [showAssetForm, setShowAssetForm] = useState(false)

  // Locations
  const [locations, setLocations] = useState<Location[]>([])
  const [locationForm, setLocationForm] = useState({ name: '', location_type: 'floor' })
  const [showLocationForm, setShowLocationForm] = useState(false)

  // Discrepancy Categories
  const [discrepancyCategories, setDiscrepancyCategories] = useState<DiscrepancyCategory[]>([])
  const [dcForm, setDcForm] = useState({ name: '', allow_delegate: false })
  const [showDcForm, setShowDcForm] = useState(false)

  // Approval Chains (linked to categories)
  const [approvalChains, setApprovalChains] = useState<ApprovalChain[]>([])
  const [chainCategoryId, setChainCategoryId] = useState<string | null>(null)
  const [chainForm, setChainForm] = useState({
    name: '',
    description: '',
    priority: 0,
    levels: [{ level: 1, assignee_type: 'role' as 'role' | 'user', role_id: '', user_id: '', auto_escalation_sla_hours: 24 }],
  })

  // ─── Fetch helpers ─────────────────────────────────────────────
  const fetchHolidays = useCallback(async () => {
    try {
      const params = activeSchoolId ? `?school_id=${activeSchoolId}` : ''
      const res = await apiFetch(`/api/v1/settings/master-data/holidays${params}`)
      if (res.ok) setHolidays(await res.json())
    } catch { /* ignore */ }
  }, [activeSchoolId])

  const fetchWorkingDays = useCallback(async () => {
    if (!activeSchoolId) return
    try {
      const res = await apiFetch(`/api/v1/settings/master-data/schools/${activeSchoolId}/working-days`)
      if (res.ok) {
        const data = await res.json()
        setWorkingDays(data.working_days || [])
      }
    } catch { /* ignore */ }
  }, [activeSchoolId])

  const fetchAssets = useCallback(async () => {
    if (!activeSchoolId) return
    try {
      const res = await apiFetch(`/api/v1/settings/master-data/schools/${activeSchoolId}/assets`)
      if (res.ok) setAssets(await res.json())
    } catch { /* ignore */ }
  }, [activeSchoolId])

  const fetchLocations = useCallback(async () => {
    if (!activeSchoolId) return
    try {
      const res = await apiFetch(`/api/v1/locations/?school_id=${activeSchoolId}&active_only=false`)
      if (res.ok) setLocations(await res.json())
    } catch { /* ignore */ }
  }, [activeSchoolId])

  const handleCreateLocation = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const res = await apiFetch('/api/v1/locations/', {
        method: 'POST',
        body: JSON.stringify(locationForm),
      })
      if (res.ok) {
        setBanner({ type: 'success', message: 'Location created' })
        setShowLocationForm(false)
        setLocationForm({ name: '', location_type: 'floor' })
        fetchLocations()
      } else {
        const err = await res.json().catch(() => null)
        setBanner({ type: 'error', message: err?.detail || 'Failed to create location' })
      }
    } catch {
      setBanner({ type: 'error', message: 'Network error' })
    }
  }

  const handleArchiveLocation = async (id: string) => {
    try {
      const res = await apiFetch(`/api/v1/locations/${id}`, { method: 'DELETE' })
      if (res.ok) {
        setBanner({ type: 'success', message: 'Location archived' })
        fetchLocations()
      } else {
        const err = await res.json().catch(() => null)
        setBanner({ type: 'error', message: err?.detail || 'Failed to archive location' })
      }
    } catch {
      setBanner({ type: 'error', message: 'Network error' })
    }
  }

  const handleRestoreLocation = async (id: string) => {
    try {
      const res = await apiFetch(`/api/v1/locations/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: 'active' }),
      })
      if (res.ok) {
        setBanner({ type: 'success', message: 'Location restored' })
        fetchLocations()
      } else {
        const err = await res.json().catch(() => null)
        setBanner({ type: 'error', message: err?.detail || 'Failed to restore location' })
      }
    } catch {
      setBanner({ type: 'error', message: 'Network error' })
    }
  }

  const fetchDiscrepancyCategories = useCallback(async () => {
    try {
      const res = await apiFetch('/api/v1/settings/master-data/discrepancy-categories')
      if (res.ok) setDiscrepancyCategories(await res.json())
    } catch { /* ignore */ }
  }, [])

  const fetchApprovalChains = useCallback(async () => {
    try {
      const res = await apiFetch('/api/v1/audit-discrepancy/approval-chains')
      if (res.ok) setApprovalChains(await res.json())
    } catch { /* ignore */ }
  }, [])

  const handleSaveApprovalChain = async (categoryId: string) => {
    try {
      const existing = approvalChains.find(c => c.category_id === categoryId)
      const payload = {
        name: chainForm.name,
        description: chainForm.description || null,
        priority: chainForm.priority,
        category_id: categoryId,
        school_id: activeSchoolId,
        levels: chainForm.levels.map(l => ({
          level: l.level,
          role_id: l.assignee_type === 'role' ? l.role_id || null : null,
          user_id: l.assignee_type === 'user' ? l.user_id || null : null,
          assignee_type: l.assignee_type,
          auto_escalation_sla_hours: l.auto_escalation_sla_hours,
        })),
      }

      const url = existing
        ? `/api/v1/audit-discrepancy/approval-chains/${existing.chain_version_id}`
        : '/api/v1/audit-discrepancy/approval-chains'
      const method = existing ? 'PATCH' : 'POST'

      const res = await apiFetch(url, { method, body: JSON.stringify(payload) })
      if (res.ok) {
        // Activate the chain
        const chain = await res.json()
        if (!chain.is_active) {
          await apiFetch(`/api/v1/audit-discrepancy/approval-chains/${chain.chain_version_id}/activate`, { method: 'PATCH' })
        }
        setBanner({ type: 'success', message: 'Approval chain saved' })
        setChainCategoryId(null)
        fetchApprovalChains()
      } else {
        const err = await res.json().catch(() => null)
        setBanner({ type: 'error', message: err?.detail || 'Failed to save chain' })
      }
    } catch {
      setBanner({ type: 'error', message: 'Network error' })
    }
  }

  const handleDeleteApprovalChain = async (chainId: string) => {
    try {
      const res = await apiFetch(`/api/v1/audit-discrepancy/approval-chains/${chainId}`, { method: 'DELETE' })
      if (res.ok) {
        setBanner({ type: 'success', message: 'Approval chain removed' })
        fetchApprovalChains()
      }
    } catch { /* ignore */ }
  }

  // ─── Initial fetch ─────────────────────────────────────────────
  useEffect(() => {
    fetchConfig()
  }, [fetchConfig])

  useEffect(() => {
    if (activeTab === 'master_data') {
      fetchHolidays()
      fetchWorkingDays()
      fetchAssets()
      fetchLocations()
      fetchDiscrepancyCategories()
      fetchApprovalChains()
    }
    if (activeTab === 'feature_flags') {
      fetchFeatureFlags()
    }
  }, [activeTab, fetchHolidays, fetchWorkingDays, fetchAssets, fetchLocations, fetchDiscrepancyCategories, fetchApprovalChains, fetchFeatureFlags])

  // ─── Settings actions ──────────────────────────────────────────
  const handleSaveConfig = async (key: string, value: string) => {
    setSavingKey(key)
    try {
      const res = await apiFetch(`/api/v1/settings/configuration/${key}`, {
        method: 'PATCH',
        body: JSON.stringify({ value, scope_type: 'global' }),
      })
      if (res.ok) {
        setBanner({ type: 'success', message: `"${key}" updated` })
        fetchConfig()
      } else {
        const err = await res.json().catch(() => null)
        setBanner({ type: 'error', message: err?.detail || 'Failed to update' })
      }
    } catch {
      setBanner({ type: 'error', message: 'Network error' })
    } finally {
      setSavingKey(null)
    }
  }

  const getConfigValue = (key: string): string => {
    const item = configItems.find(c => c.config_key === key)
    return item?.current_value ?? item?.global_default ?? ''
  }

  // ─── Holiday actions ───────────────────────────────────────────
  const handleCreateHoliday = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const res = await apiFetch('/api/v1/settings/master-data/holidays', {
        method: 'POST',
        body: JSON.stringify({
          holiday_date: holidayForm.holiday_date,
          label: holidayForm.label,
          school_id: activeSchoolId,
          recurrence_type: holidayForm.recurrence_type,
        }),
      })
      if (res.ok) {
        setBanner({ type: 'success', message: 'Holiday added' })
        setShowHolidayForm(false)
        setHolidayForm({ holiday_date: '', label: '', recurrence_type: 'one_time' })
        fetchHolidays()
      } else {
        const err = await res.json().catch(() => null)
        setBanner({ type: 'error', message: err?.detail || 'Failed to add holiday' })
      }
    } catch {
      setBanner({ type: 'error', message: 'Network error' })
    }
  }

  const handleDeleteHoliday = async (id: string) => {
    try {
      const res = await apiFetch(`/api/v1/settings/master-data/holidays/${id}`, { method: 'DELETE' })
      if (res.ok) {
        setBanner({ type: 'success', message: 'Holiday removed' })
        fetchHolidays()
      } else {
        const err = await res.json().catch(() => null)
        setBanner({ type: 'error', message: err?.detail || 'Failed to remove holiday' })
      }
    } catch {
      setBanner({ type: 'error', message: 'Network error' })
    }
  }

  // ─── Working Days actions ──────────────────────────────────────
  const handleToggleWorkingDay = async (day: string) => {
    const updated = workingDays.includes(day)
      ? workingDays.filter(d => d !== day)
      : [...workingDays, day]
    setWorkingDays(updated)
    if (!activeSchoolId) return
    try {
      const res = await apiFetch(`/api/v1/settings/master-data/schools/${activeSchoolId}/working-days`, {
        method: 'PATCH',
        body: JSON.stringify({ working_days: updated }),
      })
      if (!res.ok) setBanner({ type: 'error', message: 'Failed to update working days' })
    } catch {
      setBanner({ type: 'error', message: 'Network error' })
    }
  }

  // ─── Asset actions ─────────────────────────────────────────────
  const handleCreateAsset = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!activeSchoolId) return
    try {
      const res = await apiFetch('/api/v1/settings/master-data/assets', {
        method: 'POST',
        body: JSON.stringify({
          school_id: activeSchoolId,
          name: assetForm.name,
          category_code: assetForm.category_code || undefined,
          location_id: assetForm.location_id || undefined,
        }),
      })
      if (res.ok) {
        setBanner({ type: 'success', message: 'Asset created' })
        setShowAssetForm(false)
        setAssetForm({ name: '', category_code: '', location_id: '' })
        fetchAssets()
      } else {
        const err = await res.json().catch(() => null)
        setBanner({ type: 'error', message: err?.detail || 'Failed to create asset' })
      }
    } catch {
      setBanner({ type: 'error', message: 'Network error' })
    }
  }

  const handleRetireAsset = async (id: string) => {
    try {
      const res = await apiFetch(`/api/v1/settings/master-data/assets/${id}/retire`, { method: 'POST' })
      if (res.ok) {
        setBanner({ type: 'success', message: 'Asset retired' })
        fetchAssets()
      } else {
        const err = await res.json().catch(() => null)
        setBanner({ type: 'error', message: err?.detail || 'Failed to retire asset' })
      }
    } catch {
      setBanner({ type: 'error', message: 'Network error' })
    }
  }

  // ─── Discrepancy Category actions ──────────────────────────────
  const handleCreateDC = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const res = await apiFetch('/api/v1/settings/master-data/discrepancy-categories', {
        method: 'POST',
        body: JSON.stringify(dcForm),
      })
      if (res.ok) {
        setBanner({ type: 'success', message: 'Category created' })
        setShowDcForm(false)
        setDcForm({ name: '', allow_delegate: false })
        fetchDiscrepancyCategories()
      } else {
        const err = await res.json().catch(() => null)
        setBanner({ type: 'error', message: err?.detail || 'Failed to create category' })
      }
    } catch {
      setBanner({ type: 'error', message: 'Network error' })
    }
  }

  const handleDeprecateDC = async (id: string) => {
    try {
      const res = await apiFetch(`/api/v1/settings/master-data/discrepancy-categories/${id}/deprecate`, { method: 'POST' })
      if (res.ok) {
        setBanner({ type: 'success', message: 'Category deprecated' })
        fetchDiscrepancyCategories()
      } else {
        const err = await res.json().catch(() => null)
        setBanner({ type: 'error', message: err?.detail || 'Failed to deprecate category' })
      }
    } catch {
      setBanner({ type: 'error', message: 'Network error' })
    }
  }

  // ─── Render ────────────────────────────────────────────────────
  if (loading) return <div className="loading-state">Loading settings…</div>

  return (
    <div className="settings-master-data page-shell">
      {/* Banner */}
      {banner && (
        <div className={`alert alert-${banner.type}`}>
          <span className="alert-icon">{banner.type === 'error' ? '⚠️' : '✓'}</span>
          <span>{banner.message}</span>
          <button onClick={() => setBanner(null)} className="alert-close">×</button>
        </div>
      )}

      {/* Header */}
      <div className="header">
        <h1>Settings & Master Data</h1>
      </div>

      {error && <div className="error">{error}</div>}

      {/* Top-level tabs */}
      <div className="tabs">
        <button className={`tab ${activeTab === 'settings' ? 'active' : ''}`} onClick={() => setActiveTab('settings')}>
          Settings
        </button>
        <button className={`tab ${activeTab === 'master_data' ? 'active' : ''}`} onClick={() => setActiveTab('master_data')}>
          Master Data
        </button>
        <button className={`tab ${activeTab === 'feature_flags' ? 'active' : ''}`} onClick={() => setActiveTab('feature_flags')}>
          🚩 Feature Flags
        </button>
      </div>

      {/* ═══════════ SETTINGS TAB ═══════════ */}
      {activeTab === 'settings' && (
        <div>
          {!isSuperAdmin && (
            <p style={{ color: 'var(--ink-300)', fontSize: 'var(--text-small)', marginBottom: 'var(--space-5)' }}>
              Only SuperAdmin can edit global configuration values.
            </p>
          )}

          {configItems.length === 0 ? (
            <div className="empty-state">No configuration items found</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
              {SETTING_GROUPS.map(group => (
                <div key={group.id}>
                  {/* Group header */}
                  <div style={{ marginBottom: 'var(--space-3)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                      <span style={{ fontSize: '1.25rem' }}>{group.icon}</span>
                      <h3 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 'var(--text-h4)', color: 'var(--ink-900)' }}>
                        {group.label}
                      </h3>
                    </div>
                    <p style={{ margin: '2px 0 0', fontSize: 'var(--text-small)', color: 'var(--ink-300)' }}>
                      {group.description}
                    </p>
                  </div>

                  {/* Setting cards */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1px', background: 'var(--line)', borderRadius: 'var(--radius)', overflow: 'hidden' }}>
                    {group.items.map(item => {
                      const currentValue = getConfigValue(item.config_key)
                      const isSaving = savingKey === item.config_key

                      return (
                        <div key={item.config_key} style={{
                          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                          padding: 'var(--space-4) var(--space-5)',
                          background: 'var(--surface)',
                          opacity: isSaving ? 0.6 : 1,
                          transition: 'opacity 0.15s',
                        }}>
                          {/* Label + description */}
                          <div style={{ flex: 1, minWidth: 0, marginRight: 'var(--space-4)' }}>
                            <div style={{ fontWeight: 600, fontSize: 'var(--text-body)', color: 'var(--ink-900)' }}>
                              {item.label}
                            </div>
                            <div style={{ fontSize: 'var(--text-micro)', color: 'var(--ink-300)', marginTop: '2px', lineHeight: 1.3 }}>
                              {item.description}
                            </div>
                          </div>

                          {/* Control */}
                          <div style={{ flexShrink: 0, display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                            {item.control === 'readonly' && (
                              <span style={{
                                padding: '5px 12px', borderRadius: 'var(--radius-sm)',
                                background: 'var(--paper-1)', color: 'var(--ink-500)',
                                fontSize: 'var(--text-small)', fontWeight: 600,
                                fontFamily: 'var(--mono)',
                              }}>
                                {currentValue}
                              </span>
                            )}

                            {item.control === 'number' && (
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <input
                                  type="number"
                                  min={item.min}
                                  max={item.max}
                                  step={item.step}
                                  defaultValue={currentValue}
                                  onBlur={e => {
                                    const val = e.target.value
                                    if (val !== currentValue) handleSaveConfig(item.key, val)
                                  }}
                                  onKeyDown={e => {
                                    if (e.key === 'Enter') {
                                      const val = (e.target as HTMLInputElement).value
                                      if (val !== currentValue) handleSaveConfig(item.key, val)
                                    }
                                  }}
                                  style={{
                                    width: '80px', padding: '5px 8px', textAlign: 'right',
                                    border: '1.5px solid var(--line)', borderRadius: 'var(--radius-sm)',
                                    fontSize: 'var(--text-small)', fontWeight: 600,
                                    fontFamily: 'var(--mono)', color: 'var(--ink-900)',
                                    background: 'var(--surface)',
                                  }}
                                />
                                {item.unit && (
                                  <span style={{ fontSize: 'var(--text-micro)', color: 'var(--ink-300)', fontWeight: 500 }}>
                                    {item.unit}
                                  </span>
                                )}
                              </div>
                            )}

                            {item.control === 'select' && item.options && (
                              <select
                                defaultValue={currentValue}
                                onChange={e => handleSaveConfig(item.key, e.target.value)}
                                style={{
                                  padding: '5px 10px', borderRadius: 'var(--radius-sm)',
                                  border: '1.5px solid var(--line)',
                                  fontSize: 'var(--text-small)', fontWeight: 500,
                                  color: 'var(--ink-900)', background: 'var(--surface)',
                                  cursor: 'pointer', minWidth: '160px',
                                }}
                              >
                                {item.options.map(opt => (
                                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                                ))}
                              </select>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ═══════════ MASTER DATA TAB ═══════════ */}
      {activeTab === 'master_data' && (
        <div>
          {!activeSchoolId && (
            <div className="alert alert-error" style={{ marginBottom: 'var(--space-4)' }}>
              <span>Select a school from the top bar to manage master data.</span>
            </div>
          )}

          {/* Master Data sub-tabs */}
          <div className="tabs" style={{ marginBottom: 'var(--space-5)' }}>
            <button className={`tab ${masterTab === 'holidays' ? 'active' : ''}`} onClick={() => setMasterTab('holidays')}>
              🗓️ Holidays
            </button>
            <button className={`tab ${masterTab === 'working_days' ? 'active' : ''}`} onClick={() => setMasterTab('working_days')}>
              📅 Working Days
            </button>
            <button className={`tab ${masterTab === 'locations' ? 'active' : ''}`} onClick={() => setMasterTab('locations')}>
              📍 Locations
            </button>
            <button className={`tab ${masterTab === 'assets' ? 'active' : ''}`} onClick={() => setMasterTab('assets')}>
              🏢 Assets
            </button>
            <button className={`tab ${masterTab === 'discrepancy_categories' ? 'active' : ''}`} onClick={() => setMasterTab('discrepancy_categories')}>
              ⚠️ Discrepancy Categories
            </button>
          </div>

          {/* ─── Holidays ─── */}
          {masterTab === 'holidays' && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-4)' }}>
                <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 'var(--text-h3)' }}>Holiday Calendar</h2>
                {(isSuperAdmin || isAdmin) && (
                  <button className="btn btn-primary btn-sm" onClick={() => setShowHolidayForm(!showHolidayForm)}>
                    {showHolidayForm ? 'Cancel' : '+ Add Holiday'}
                  </button>
                )}
              </div>

              {showHolidayForm && (
                <form onSubmit={handleCreateHoliday} className="config-form" style={{ marginBottom: 'var(--space-5)' }}>
                  <div className="form-row">
                    <div className="form-group">
                      <label htmlFor="holiday_date">Date *</label>
                      <input id="holiday_date" type="date" required value={holidayForm.holiday_date}
                        onChange={e => setHolidayForm(p => ({ ...p, holiday_date: e.target.value }))} />
                    </div>
                    <div className="form-group">
                      <label htmlFor="holiday_label">Label *</label>
                      <input id="holiday_label" type="text" required placeholder="e.g. Republic Day" value={holidayForm.label}
                        onChange={e => setHolidayForm(p => ({ ...p, label: e.target.value }))} />
                    </div>
                    <div className="form-group">
                      <label htmlFor="holiday_recurrence">Recurrence</label>
                      <select id="holiday_recurrence" value={holidayForm.recurrence_type}
                        onChange={e => setHolidayForm(p => ({ ...p, recurrence_type: e.target.value }))}>
                        <option value="one_time">One-time</option>
                        <option value="annual">Annual</option>
                      </select>
                    </div>
                  </div>
                  <div className="form-actions">
                    <button type="submit" className="btn btn-primary btn-sm">Save Holiday</button>
                  </div>
                </form>
              )}

              {holidays.length === 0 ? (
                <div className="empty-state">No holidays configured</div>
              ) : (
                <div className="table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Label</th>
                        <th>Recurrence</th>
                        <th>Scope</th>
                        {(isSuperAdmin || isAdmin) && <th>Actions</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {holidays.map(h => (
                        <tr key={h.id}>
                          <td><code>{formatDate(h.holiday_date)}</code></td>
                          <td style={{ fontWeight: 600 }}>{h.label}</td>
                          <td>
                            <span className="status status-active">{h.recurrence_type}</span>
                          </td>
                          <td style={{ fontSize: 'var(--text-small)', color: 'var(--ink-300)' }}>
                            {h.school_id ? 'School' : 'Organization'}
                          </td>
                          {(isSuperAdmin || isAdmin) && (
                            <td>                                <button className="btn btn-sm btn-danger" onClick={() => setConfirmAction({ label: `Remove "${h.label}" from the holiday calendar?`, onConfirm: () => handleDeleteHoliday(h.id) })}>
                                  Remove
                                </button>
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* ─── Working Days ─── */}
          {masterTab === 'working_days' && (
            <div>
              <div style={{ marginBottom: 'var(--space-4)' }}>
                <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 'var(--text-h3)' }}>Working Days</h2>
                <p style={{ color: 'var(--ink-300)', fontSize: 'var(--text-small)', marginTop: 'var(--space-2)' }}>
                  Configure which days of the week are working days for compliance scheduling.
                </p>
              </div>

              <div className="config-form">
                <div style={{ display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
                  {WORKING_DAY_OPTIONS.map(day => {
                    const isActive = workingDays.map(d => d.toLowerCase().slice(0, 3)).includes(day)
                    const fullDay = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][WORKING_DAY_OPTIONS.indexOf(day)]
                    return (
                      <button
                        key={day}
                        type="button"
                        onClick={() => handleToggleWorkingDay(day)}
                        style={{
                          padding: '12px 20px',
                          borderRadius: 'var(--radius)',
                          border: `2px solid ${isActive ? 'var(--moss-600)' : 'var(--line)'}`,
                          background: isActive ? 'var(--moss-100)' : 'var(--surface)',
                          color: isActive ? 'var(--moss-600)' : 'var(--ink-500)',
                          fontWeight: 600,
                          fontSize: 'var(--text-small)',
                          cursor: 'pointer',
                          transition: 'all 0.15s var(--ease)',
                          minWidth: '80px',
                          textAlign: 'center',
                        }}
                      >
                        {fullDay}
                      </button>
                    )
                  })}
                </div>
                <p style={{ marginTop: 'var(--space-4)', fontSize: 'var(--text-micro)', color: 'var(--ink-300)' }}>
                  Click to toggle. Changes save automatically.
                </p>
              </div>
            </div>
          )}

          {/* ─── Locations ─── */}
          {masterTab === 'locations' && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-4)' }}>
                <div>
                  <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 'var(--text-h3)' }}>Locations</h2>
                  <p style={{ color: 'var(--ink-300)', fontSize: 'var(--text-small)', marginTop: 'var(--space-1)' }}>
                    Floors, zones, wings, and buildings used to scope observations and assets.
                  </p>
                </div>
                {(isSuperAdmin || isAdmin) && (
                  <button className="btn btn-primary btn-sm" onClick={() => setShowLocationForm(!showLocationForm)}>
                    {showLocationForm ? 'Cancel' : '+ Add Location'}
                  </button>
                )}
              </div>

              {showLocationForm && (
                <form onSubmit={handleCreateLocation} className="config-form" style={{ marginBottom: 'var(--space-5)' }}>
                  <div className="form-row">
                    <div className="form-group" style={{ flex: 2 }}>
                      <label htmlFor="loc_name">Name *</label>
                      <input id="loc_name" type="text" required placeholder="e.g. Floor 1, Building A, North Wing" value={locationForm.name}
                        onChange={e => setLocationForm(p => ({ ...p, name: e.target.value }))} />
                    </div>
                    <div className="form-group" style={{ flex: 1 }}>
                      <label htmlFor="loc_type">Type</label>
                      <select id="loc_type" value={locationForm.location_type}
                        onChange={e => setLocationForm(p => ({ ...p, location_type: e.target.value }))}>
                        <option value="floor">Floor</option>
                        <option value="zone">Zone</option>
                        <option value="wing">Wing</option>
                        <option value="building">Building</option>
                      </select>
                    </div>
                  </div>
                  <div className="form-actions">
                    <button type="submit" className="btn btn-primary btn-sm">Create Location</button>
                  </div>
                </form>
              )}

              {locations.length === 0 ? (
                <div className="empty-state">No locations configured</div>
              ) : (
                <div className="table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>Type</th>
                        <th>Status</th>
                        <th>Created</th>
                        {(isSuperAdmin || isAdmin) && <th>Actions</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {locations.map(loc => (
                        <tr key={loc.id}>
                          <td style={{ fontWeight: 600 }}>{loc.name}</td>
                          <td>
                            <span className="status status-active" style={{ textTransform: 'capitalize' }}>
                              {loc.location_type}
                            </span>
                          </td>
                          <td>
                            <span className={`status status-${loc.status === 'active' ? 'active' : 'deprecated'}`}>
                              {loc.status}
                            </span>
                          </td>
                          <td style={{ fontSize: 'var(--text-small)', color: 'var(--ink-300)' }}>
                            {new Date(loc.created_at).toLocaleDateString()}
                          </td>
                          {(isSuperAdmin || isAdmin) && (
                            <td>
                              {loc.status === 'active' ? (
                                <button className="btn btn-sm btn-danger" onClick={() => setConfirmAction({ label: `Archive location "${loc.name}"? It can be restored later.`, onConfirm: () => handleArchiveLocation(loc.id) })}>
                                  Archive
                                </button>
                              ) : (
                                <button className="btn btn-sm" onClick={() => handleRestoreLocation(loc.id)}>
                                  Restore
                                </button>
                              )}
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* ─── Assets ─── */}
          {masterTab === 'assets' && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-4)' }}>
                <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 'var(--text-h3)' }}>Assets</h2>
                {(isSuperAdmin || isAdmin) && (
                  <button className="btn btn-primary btn-sm" onClick={() => setShowAssetForm(!showAssetForm)}>
                    {showAssetForm ? 'Cancel' : '+ Add Asset'}
                  </button>
                )}
              </div>

              {showAssetForm && (
                <form onSubmit={handleCreateAsset} className="config-form" style={{ marginBottom: 'var(--space-5)' }}>
                  <div className="form-row">
                    <div className="form-group">
                      <label htmlFor="asset_name">Name *</label>
                      <input id="asset_name" type="text" required placeholder="e.g. Projector - Room 101" value={assetForm.name}
                        onChange={e => setAssetForm(p => ({ ...p, name: e.target.value }))} />
                    </div>
                    <div className="form-group">
                      <label htmlFor="asset_category">Category Code</label>
                      <input id="asset_category" type="text" placeholder="e.g. AV_EQUIPMENT" value={assetForm.category_code}
                        onChange={e => setAssetForm(p => ({ ...p, category_code: e.target.value }))} />
                    </div>
                  </div>
                  <div className="form-actions">
                    <button type="submit" className="btn btn-primary btn-sm">Create Asset</button>
                  </div>
                </form>
              )}

              {assets.length === 0 ? (
                <div className="empty-state">No assets registered</div>
              ) : (
                <div className="table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>Category</th>
                        <th>Status</th>
                        <th>Created</th>
                        {(isSuperAdmin || isAdmin) && <th>Actions</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {assets.map(a => (
                        <tr key={a.id}>
                          <td style={{ fontWeight: 600 }}>{a.name}</td>
                          <td><code style={{ fontSize: 'var(--text-small)' }}>{a.category_code || '—'}</code></td>
                          <td>
                            <span className={`status status-${a.status === 'active' ? 'active' : 'deprecated'}`}>
                              {a.status}
                            </span>
                          </td>
                          <td style={{ fontSize: 'var(--text-small)', color: 'var(--ink-300)' }}>
                            {new Date(a.created_at).toLocaleDateString()}
                          </td>
                          {(isSuperAdmin || isAdmin) && (
                            <td>
                              {a.status === 'active' && (
                                <button className="btn btn-sm btn-danger" onClick={() => setConfirmAction({ label: `Retire asset "${a.name}"? It will no longer be available for new observations.`, onConfirm: () => handleRetireAsset(a.id) })}>
                                  Retire
                                </button>
                              )}
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* ─── Discrepancy Categories ─── */}
          {masterTab === 'discrepancy_categories' && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-4)' }}>
                <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 'var(--text-h3)' }}>Discrepancy Categories</h2>
                {isSuperAdmin && (
                  <button className="btn btn-primary btn-sm" onClick={() => setShowDcForm(!showDcForm)}>
                    {showDcForm ? 'Cancel' : '+ Add Category'}
                  </button>
                )}
              </div>

              {showDcForm && (
                <form onSubmit={handleCreateDC} className="config-form" style={{ marginBottom: 'var(--space-5)' }}>
                  <div className="form-row">
                    <div className="form-group">
                      <label htmlFor="dc_name">Name *</label>
                      <input id="dc_name" type="text" required placeholder="e.g. Safety Violation" value={dcForm.name}
                        onChange={e => setDcForm(p => ({ ...p, name: e.target.value }))} />
                    </div>
                    <div className="form-group">
                      <label className="checkbox-label" style={{ marginTop: '1.5rem' }}>
                        <input type="checkbox" checked={dcForm.allow_delegate}
                          onChange={e => setDcForm(p => ({ ...p, allow_delegate: e.target.checked }))} />
                        <span>Allow delegation</span>
                      </label>
                    </div>
                  </div>
                  <div className="form-actions">
                    <button type="submit" className="btn btn-primary btn-sm">Create Category</button>
                  </div>
                </form>
              )}

              {discrepancyCategories.length === 0 ? (
                <div className="empty-state">No discrepancy categories configured</div>
              ) : (
                <div className="table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>Status</th>
                        <th>Approval Chain</th>
                        <th>Allow Delegation</th>
                        <th>Created</th>
                        {isSuperAdmin && <th>Actions</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {discrepancyCategories.map(dc => {
                        const chain = approvalChains.find(c => c.category_id === dc.id)
                        const isEditingChain = chainCategoryId === dc.id

                        return (
                          <React.Fragment key={dc.id}>
                            <tr>
                              <td style={{ fontWeight: 600 }}>{dc.name}</td>
                              <td>
                                <span className={`status status-${dc.status === 'active' ? 'active' : 'deprecated'}`}>
                                  {dc.status}
                                </span>
                              </td>
                              <td>
                                {chain ? (
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                    <span className={`status ${chain.is_active ? 'status-active' : 'status-deprecated'}`}>
                                      {chain.is_active ? 'Active' : 'Inactive'}
                                    </span>
                                    <span style={{ fontSize: 'var(--text-small)', color: 'var(--ink-500)' }}>
                                      {chain.name} ({chain.levels.length}L)
                                    </span>
                                  </div>
                                ) : (
                                  <span style={{ fontSize: 'var(--text-small)', color: 'var(--ink-300)' }}>None</span>
                                )}
                              </td>
                              <td>{dc.allow_delegate ? '✓' : '—'}</td>
                              <td style={{ fontSize: 'var(--text-small)', color: 'var(--ink-300)' }}>
                                {new Date(dc.created_at).toLocaleDateString()}
                              </td>
                              {isSuperAdmin && (
                                <td>
                                  <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                                    <button
                                      className="btn btn-sm"
                                      onClick={() => {
                                        if (isEditingChain) {
                                          setChainCategoryId(null)
                                        } else {
                                          setChainCategoryId(dc.id)
                                          if (chain) {
                                            setChainForm({
                                              name: chain.name,
                                              description: chain.description || '',
                                              priority: chain.priority,
                                              levels: chain.levels.map((l, i) => ({
                                                level: i + 1,
                                                assignee_type: l.assignee_type || 'role',
                                                role_id: l.role_id || '',
                                                user_id: l.user_id || '',
                                                auto_escalation_sla_hours: l.auto_escalation_sla_hours || 24,
                                              })),
                                            })
                                          } else {
                                            setChainForm({
                                              name: `${dc.name} Chain`,
                                              description: '',
                                              priority: 0,
                                              levels: [{ level: 1, assignee_type: 'role', role_id: '', user_id: '', auto_escalation_sla_hours: 24 }],
                                            })
                                          }
                                        }
                                      }}
                                    >
                                      {isEditingChain ? 'Cancel' : chain ? 'Edit Chain' : '+ Chain'}
                                    </button>
                                    {dc.status === 'active' && !isEditingChain && (
                                      <button className="btn btn-sm btn-danger" onClick={() => setConfirmAction({ label: `Deprecate category "${dc.name}"? Existing discrepancies using this category will be unaffected.`, onConfirm: () => handleDeprecateDC(dc.id) })}>
                                        Deprecate
                                      </button>
                                    )}
                                  </div>
                                </td>
                              )}
                            </tr>

                            {/* Inline approval chain editor */}
                            {isEditingChain && (
                              <tr>
                                <td colSpan={6} style={{ padding: 'var(--space-4) var(--space-5)', background: 'var(--paper-0)' }}>
                                  <div style={{
                                    border: '1.5px solid var(--gold-600)', borderRadius: 'var(--radius)',
                                    padding: 'var(--space-4)', background: 'var(--surface)',
                                  }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-3)' }}>
                                      <h4 style={{ margin: 0, fontSize: 'var(--text-body)', color: 'var(--ink-900)' }}>
                                        {chain ? 'Edit' : 'Create'} Approval Chain for {dc.name}
                                      </h4>
                                      {chain && (
                                        <button
                                          className="btn btn-sm btn-danger"
                                          onClick={() => { handleDeleteApprovalChain(chain.chain_version_id); setChainCategoryId(null) }}
                                        >
                                          Remove Chain
                                        </button>
                                      )}
                                    </div>

                                    <div className="form-row" style={{ marginBottom: 'var(--space-3)' }}>
                                      <div className="form-group" style={{ flex: 2 }}>
                                        <label>Chain Name *</label>
                                        <input type="text" value={chainForm.name} required
                                          onChange={e => setChainForm(p => ({ ...p, name: e.target.value }))}
                                          placeholder="e.g. Safety Review Chain"
                                          style={{ padding: '6px 10px', fontSize: 'var(--text-small)' }} />
                                      </div>
                                      <div className="form-group" style={{ flex: 1 }}>
                                        <label>Priority</label>
                                        <input type="number" value={chainForm.priority}
                                          onChange={e => setChainForm(p => ({ ...p, priority: parseInt(e.target.value) || 0 }))}
                                          style={{ padding: '6px 10px', fontSize: 'var(--text-small)' }} />
                                      </div>
                                    </div>

                                    {/* Approval Levels */}
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-2)' }}>
                                      <span style={{ fontWeight: 600, fontSize: 'var(--text-small)', color: 'var(--ink-500)' }}>APPROVAL LEVELS</span>
                                      <button type="button" className="btn btn-sm btn-ghost"
                                        onClick={() => setChainForm(p => ({
                                          ...p,
                                          levels: [...p.levels, { level: p.levels.length + 1, assignee_type: 'role', role_id: '', user_id: '', auto_escalation_sla_hours: 24 }],
                                        }))}>
                                        + Level
                                      </button>
                                    </div>

                                    {chainForm.levels.map((lvl, idx) => (
                                      <div key={idx} style={{
                                        display: 'flex', gap: 'var(--space-3)', alignItems: 'flex-end',
                                        padding: '8px 12px', background: 'var(--paper-1)', borderRadius: 'var(--radius-sm)',
                                        marginBottom: '6px',
                                      }}>
                                        <span style={{ fontWeight: 700, fontSize: 'var(--text-micro)', color: 'var(--ink-300)', minWidth: '20px' }}>
                                          L{lvl.level}
                                        </span>
                                        <div style={{ flex: 1 }}>
                                          <select value={lvl.assignee_type}
                                            onChange={e => {
                                              const val = e.target.value as 'role' | 'user'
                                              setChainForm(p => ({
                                                ...p,
                                                levels: p.levels.map((l, i) => i === idx ? { ...l, assignee_type: val, role_id: '', user_id: '' } : l),
                                              }))
                                            }}
                                            style={{ width: '100%', padding: '5px 8px', fontSize: 'var(--text-small)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--line)' }}>
                                            <option value="role">Role</option>
                                            <option value="user">Person</option>
                                          </select>
                                        </div>
                                        <div style={{ flex: 2 }}>
                                          {lvl.assignee_type === 'role' ? (
                                            <select value={lvl.role_id}
                                              onChange={e => setChainForm(p => ({
                                                ...p,
                                                levels: p.levels.map((l, i) => i === idx ? { ...l, role_id: e.target.value } : l),
                                              }))}
                                              style={{ width: '100%', padding: '5px 8px', fontSize: 'var(--text-small)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--line)' }}>
                                              <option value="">Select role…</option>
                                              <option value="superadmin">SuperAdmin</option>
                                              <option value="admin">Admin</option>
                                              <option value="auditor">Auditor</option>
                                              <option value="dept_head">Dept Head</option>
                                              <option value="checker">Checker</option>
                                            </select>
                                          ) : (
                                            <input type="text" placeholder="User ID"
                                              value={lvl.user_id}
                                              onChange={e => setChainForm(p => ({
                                                ...p,
                                                levels: p.levels.map((l, i) => i === idx ? { ...l, user_id: e.target.value } : l),
                                              }))}
                                              style={{ width: '100%', padding: '5px 8px', fontSize: 'var(--text-small)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--line)' }} />
                                          )}
                                        </div>
                                        <div style={{ flex: 0.5 }}>
                                          <div style={{ fontSize: 'var(--text-micro)', color: 'var(--ink-300)', marginBottom: '2px' }}>SLA hrs</div>
                                          <input type="number" min={1} value={lvl.auto_escalation_sla_hours}
                                            onChange={e => setChainForm(p => ({
                                              ...p,
                                              levels: p.levels.map((l, i) => i === idx ? { ...l, auto_escalation_sla_hours: parseInt(e.target.value) || 24 } : l),
                                            }))}
                                            title="Auto-escalation SLA in hours"
                                            style={{ width: '100%', padding: '5px 8px', fontSize: 'var(--text-small)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--line)' }} />
                                        </div>
                                        {chainForm.levels.length > 1 && (
                                          <button type="button" className="btn btn-sm btn-ghost"
                                            style={{ color: 'var(--rose-600)', minWidth: 'auto', padding: '4px 8px' }}
                                            onClick={() => setChainForm(p => ({
                                              ...p,
                                              levels: p.levels.filter((_, i) => i !== idx).map((l, i) => ({ ...l, level: i + 1 })),
                                            }))}>
                                            ✕
                                          </button>
                                        )}
                                      </div>
                                    ))}

                                    <div style={{ marginTop: 'var(--space-3)', display: 'flex', gap: 'var(--space-2)' }}>
                                      <button className="btn btn-primary btn-sm" onClick={() => handleSaveApprovalChain(dc.id)}>
                                        Save Chain
                                      </button>
                                      <button className="btn btn-sm" onClick={() => setChainCategoryId(null)}>
                                        Cancel
                                      </button>
                                    </div>
                                  </div>
                                </td>
                              </tr>
                            )}
                          </React.Fragment>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ═══════════ FEATURE FLAGS TAB ═══════════ */}
      {activeTab === 'feature_flags' && (
        <div>
          <div style={{ marginBottom: 'var(--space-4)' }}>
            <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 'var(--text-h3)' }}>Feature Flags</h2>
            <p style={{ color: 'var(--ink-300)', fontSize: 'var(--text-small)', marginTop: 'var(--space-2)' }}>
              Toggle features on or off for phased rollout. Changes take effect immediately.
            </p>
          </div>

          {!isSuperAdmin && (
            <p style={{ color: 'var(--ink-300)', fontSize: 'var(--text-small)', marginBottom: 'var(--space-4)' }}>
              Only SuperAdmin can toggle feature flags.
            </p>
          )}

          {featureFlags.length === 0 ? (
            <div className="empty-state">No feature flags configured</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
              {featureFlags.map(flag => (
                <div
                  key={flag.flag_key}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: 'var(--space-4) var(--space-5)',
                    background: 'var(--surface)',
                    border: '1px solid var(--line)',
                    borderRadius: 'var(--radius)',
                    boxShadow: 'var(--shadow)',
                    transition: 'border-color 0.15s var(--ease)',
                    borderColor: flag.enabled ? 'var(--moss-600)' : 'var(--line)',
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                      <span style={{
                        fontWeight: 600,
                        fontSize: 'var(--text-body)',
                        color: 'var(--ink-900)',
                        fontFamily: 'var(--mono)',
                      }}>
                        {flag.flag_key}
                      </span>
                      <span className={`status ${flag.enabled ? 'status-active' : 'status-deprecated'}`}>
                        {flag.enabled ? 'ON' : 'OFF'}
                      </span>
                    </div>
                    {flag.description && (
                      <p style={{
                        margin: '4px 0 0',
                        fontSize: 'var(--text-small)',
                        color: 'var(--ink-300)',
                        lineHeight: 1.4,
                      }}>
                        {flag.description}
                      </p>
                    )}
                  </div>

                  {isSuperAdmin && (
                    <button
                      onClick={() => handleToggleFlag(flag.flag_key, flag.enabled)}
                      style={{
                        position: 'relative',
                        width: '52px',
                        height: '28px',
                        borderRadius: '14px',
                        border: 'none',
                        cursor: 'pointer',
                        background: flag.enabled ? 'var(--moss-600)' : 'var(--ink-200)',
                        transition: 'background 0.2s var(--ease)',
                        flexShrink: 0,
                        marginLeft: 'var(--space-4)',
                      }}
                      title={flag.enabled ? 'Click to disable' : 'Click to enable'}
                    >
                      <span style={{
                        position: 'absolute',
                        top: '3px',
                        left: flag.enabled ? '27px' : '3px',
                        width: '22px',
                        height: '22px',
                        borderRadius: '50%',
                        background: '#fff',
                        boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
                        transition: 'left 0.2s var(--ease)',
                      }} />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Confirmation dialog */}
      {confirmAction && (
        <div
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
          }}
          onClick={e => { if (e.target === e.currentTarget) setConfirmAction(null) }}
        >
          <div style={{
            background: 'var(--surface)', borderRadius: 'var(--radius-lg)',
            padding: 'var(--space-6)', maxWidth: '400px', width: '90%',
            boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
          }}>
            <h3 style={{ margin: '0 0 var(--space-3)', fontSize: 'var(--text-body)', fontWeight: 700, color: 'var(--ink-900)' }}>
              Are you sure?
            </h3>
            <p style={{ margin: '0 0 var(--space-5)', fontSize: 'var(--text-small)', color: 'var(--ink-500)', lineHeight: 1.5 }}>
              {confirmAction.label}
            </p>
            <div style={{ display: 'flex', gap: 'var(--space-3)', justifyContent: 'flex-end' }}>
              <button className="btn btn-sm" onClick={() => setConfirmAction(null)}>Cancel</button>
              <button className="btn btn-sm btn-danger" onClick={() => { confirmAction.onConfirm(); setConfirmAction(null) }}>
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
