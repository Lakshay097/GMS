import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import {
  Search,
  X,
  ClipboardList,
  Eye,
  User,
  School,
  FolderOpen,
  Target,
  BarChart2,
  FileText,
  Loader2,
  ArrowRight,
} from 'lucide-react'
import './CommandPalette.css'

/* ── Types ─────────────────────────────────────────────────────────────── */

interface SearchHit {
  entity_type: string
  entity_id: string
  title: string
  description?: string
  status?: string
  score?: number
  created_at?: string
}

interface SearchApiResponse {
  hits: SearchHit[]
  total_hits: number
  processing_time_ms: number
}

/* ── Config ────────────────────────────────────────────────────────────── */

const ENTITY_TYPES = [
  { value: 'task', label: 'Tasks', icon: ClipboardList, color: 'var(--gold-600)' },
  { value: 'observation', label: 'Observations', icon: Eye, color: 'var(--moss-600)' },
  { value: 'user', label: 'Users', icon: User, color: 'var(--blue-500)' },
  { value: 'school', label: 'Schools', icon: School, color: 'var(--gold-500)' },
  { value: 'department', label: 'Departments', icon: FolderOpen, color: 'var(--moss-500)' },
  { value: 'kra', label: 'KRAs', icon: Target, color: 'var(--rose-500)' },
  { value: 'kpi', label: 'KPIs', icon: BarChart2, color: 'var(--blue-600)' },
  { value: 'discrepancy', label: 'Discrepancies', icon: FileText, color: 'var(--rose-600)' },
]

function getEntityConfig(type: string) {
  return ENTITY_TYPES.find(e => e.value === type) || { label: type, icon: FileText, color: 'var(--ink-300)' }
}

function getEntityPath(hit: SearchHit): string {
  const id = hit.entity_id
  switch (hit.entity_type) {
    case 'task': return `/tasks/${id}`
    case 'observation': return `/observations/${id}`
    case 'user': return `/users/${id}/edit`
    case 'school': return `/schools/${id}/edit`
    case 'department': return `/departments/${id}/edit`
    case 'kra': return `/kra/${id}/edit`
    case 'kpi': return `/kpi/${id}/edit`
    case 'discrepancy': return `/discrepancies/${id}`
    default: return '#'
  }
}

/* ── Main Component ────────────────────────────────────────────────────── */

interface CommandPaletteProps {
  open: boolean
  onClose: () => void
}

export default function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchHit[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [activeFilter, setActiveFilter] = useState<string | null>(null)

  // Debounce timer
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  /* ── Focus input on open ──────────────────────────────────────────── */

  useEffect(() => {
    if (open) {
      setQuery('')
      setResults([])
      setSelectedIndex(0)
      setActiveFilter(null)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  /* ── Keyboard shortcut ────────────────────────────────────────────── */

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        if (open) {
          onClose()
        } else {
          // Dispatch custom event to open
          window.dispatchEvent(new CustomEvent('open-command-palette'))
        }
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onClose])

  /* ── Search with debounce ─────────────────────────────────────────── */

  const doSearch = useCallback(async (searchQuery: string) => {
    if (!searchQuery.trim()) {
      setResults([])
      return
    }

    try {
      setLoading(true)
      const params = new URLSearchParams({
        q: searchQuery.trim(),
        page: '1',
        page_size: '20',
      })
      if (activeFilter) {
        params.set('entity_types', activeFilter)
      }

      const response = await apiFetch(`/api/v1/search?${params}`)
      if (!response.ok) throw new Error('Search failed')

      const data: SearchApiResponse = await response.json()
      setResults(data.hits || [])
      setSelectedIndex(0)
    } catch {
      setResults([])
    } finally {
      setLoading(false)
    }
  }, [activeFilter])

  const handleQueryChange = (value: string) => {
    setQuery(value)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => doSearch(value), 250)
  }

  /* ── Group results by entity type ─────────────────────────────────── */

  const groupedResults = results.reduce<Record<string, SearchHit[]>>((acc, hit) => {
    if (!acc[hit.entity_type]) acc[hit.entity_type] = []
    acc[hit.entity_type].push(hit)
    return acc
  }, {})

  // Flatten for keyboard navigation
  const flatResults = results
  const totalGroups = Object.keys(groupedResults).length

  /* ── Keyboard navigation ──────────────────────────────────────────── */

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      onClose()
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex(prev => Math.min(prev + 1, flatResults.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex(prev => Math.max(prev - 1, 0))
    } else if (e.key === 'Enter' && flatResults[selectedIndex]) {
      e.preventDefault()
      navigateToResult(flatResults[selectedIndex])
    }
  }

  const navigateToResult = (hit: SearchHit) => {
    const path = getEntityPath(hit)
    if (path !== '#') {
      navigate(path)
      onClose()
    }
  }

  /* ── Scroll selected into view ────────────────────────────────────── */

  useEffect(() => {
    const el = listRef.current?.querySelector(`[data-index="${selectedIndex}"]`)
    el?.scrollIntoView({ block: 'nearest' })
  }, [selectedIndex])

  /* ── Don't render if closed ───────────────────────────────────────── */

  if (!open) return null

  /* ── Render ───────────────────────────────────────────────────────── */

  let runningIndex = -1

  return (
    <div className="cp-overlay" onClick={onClose}>
      <div className="cp-dialog" onClick={e => e.stopPropagation()}>

        {/* Search Input */}
        <div className="cp-input-row">
          <Search size={20} className="cp-input-icon" />
          <input
            ref={inputRef}
            type="text"
            className="cp-input"
            value={query}
            onChange={e => handleQueryChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search tasks, users, schools..."
            autoComplete="off"
            spellCheck={false}
          />
          <div className="cp-input-right">
            {loading && <Loader2 size={16} className="cp-spinner" />}
            <kbd className="cp-kbd">ESC</kbd>
          </div>
        </div>

        {/* Filter chips */}
        <div className="cp-filters">
          <button
            className={`cp-filter-chip ${activeFilter === null ? 'cp-filter-chip--active' : ''}`}
            onClick={() => setActiveFilter(null)}
          >
            All
          </button>
          {ENTITY_TYPES.slice(0, 5).map(et => (
            <button
              key={et.value}
              className={`cp-filter-chip ${activeFilter === et.value ? 'cp-filter-chip--active' : ''}`}
              onClick={() => setActiveFilter(activeFilter === et.value ? null : et.value)}
            >
              {et.label}
            </button>
          ))}
        </div>

        {/* Results */}
        <div className="cp-results" ref={listRef}>
          {query && !loading && results.length === 0 && (
            <div className="cp-empty">
              <p>No results for &ldquo;{query}&rdquo;</p>
              <p className="cp-empty-hint">Try different keywords or adjust filters</p>
            </div>
          )}

          {!query && (
            <div className="cp-empty">
              <p className="cp-empty-hint">Type to search across all entities</p>
            </div>
          )}

          {Object.entries(groupedResults).map(([entityType, hits]) => {
            const config = getEntityConfig(entityType)
            const Icon = config.icon

            return (
              <div key={entityType} className="cp-group">
                <div className="cp-group-header">
                  <Icon size={14} style={{ color: config.color }} />
                  <span>{config.label}</span>
                  <span className="cp-group-count">{hits.length}</span>
                </div>
                {hits.map(hit => {
                  runningIndex++
                  const idx = runningIndex
                  return (
                    <button
                      key={`${hit.entity_id}-${idx}`}
                      className={`cp-result ${idx === selectedIndex ? 'cp-result--selected' : ''}`}
                      data-index={idx}
                      onClick={() => navigateToResult(hit)}
                      onMouseEnter={() => setSelectedIndex(idx)}
                    >
                      <div className="cp-result-body">
                        <div className="cp-result-title">{hit.title}</div>
                        {hit.description && (
                          <div className="cp-result-desc">{hit.description}</div>
                        )}
                      </div>
                      <ArrowRight size={14} className="cp-result-arrow" />
                    </button>
                  )
                })}
              </div>
            )
          })}
        </div>

        {/* Footer */}
        <div className="cp-footer">
          <span><kbd>↑</kbd><kbd>↓</kbd> navigate</span>
          <span><kbd>↵</kbd> open</span>
          <span><kbd>esc</kbd> close</span>
        </div>
      </div>
    </div>
  )
}
