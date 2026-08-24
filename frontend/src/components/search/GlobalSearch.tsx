import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import {
  Search,
  Filter,
  ChevronDown,
  ChevronUp,
  X,
  ClipboardList,
  Eye,
  User,
  School,
  FolderOpen,
  Target,
  BarChart2,
  FileText,
  SearchX,
  Loader2,
} from 'lucide-react'
import './GlobalSearch.css'

/* ── Types ────────────────────────────────────────────────────────────────── */

interface SearchHit {
  entity_type: string
  entity_id: string
  school_id?: string
  department_id?: string
  title: string
  description?: string
  status?: string
  score?: number
  created_at?: string
}

interface SearchApiResponse {
  query: string
  total_hits: number
  page: number
  page_size: number
  processing_time_ms: number
  hits: SearchHit[]
}

/* ── Entity type config ──────────────────────────────────────────────────── */

const ENTITY_TYPES = [
  { value: 'task', label: 'Tasks', icon: ClipboardList },
  { value: 'observation', label: 'Observations', icon: Eye },
  { value: 'user', label: 'Users', icon: User },
  { value: 'school', label: 'Schools', icon: School },
  { value: 'department', label: 'Departments', icon: FolderOpen },
  { value: 'kra', label: 'KRAs', icon: Target },
  { value: 'kpi', label: 'KPIs', icon: BarChart2 },
  { value: 'discrepancy', label: 'Discrepancies', icon: FileText },
]

/* Map entity type → navigation path (resolved names, not raw IDs) */
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

function getEntityIcon(type: string) {
  const config = ENTITY_TYPES.find((e) => e.value === type)
  return config?.icon ?? FileText
}

function getEntityLabel(type: string) {
  const config = ENTITY_TYPES.find((e) => e.value === type)
  return config?.label ?? type
}

/* ── Date formatting ──────────────────────────────────────────────────────── */

function formatRelativeDate(dateStr?: string): string {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays} days ago`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`
  return date.toLocaleDateString()
}

/* ── Main Component ──────────────────────────────────────────────────────── */

export default function GlobalSearch() {
  const navigate = useNavigate()

  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchHit[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [hasSearched, setHasSearched] = useState(false)

  // Filters
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set())
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [filtersExpanded, setFiltersExpanded] = useState(false)

  const hasActiveFilters = selectedTypes.size > 0 || dateFrom || dateTo

  /* ── Search ──────────────────────────────────────────────────────────── */

  const doSearch = useCallback(
    async (searchQuery: string, searchPage: number, append: boolean) => {
      if (!searchQuery.trim()) return

      try {
        setLoading(true)
        setError(null)

        const params = new URLSearchParams({
          q: searchQuery.trim(),
          page: searchPage.toString(),
          page_size: '20',
        })
        if (selectedTypes.size > 0) {
          params.set('entity_types', Array.from(selectedTypes).join(','))
        }
        if (dateFrom) params.set('date_from', dateFrom)
        if (dateTo) params.set('date_to', dateTo)

        const response = await apiFetch(`/api/v1/search?${params}`)
        if (!response.ok) throw new Error('Search failed')

        const data: SearchApiResponse = await response.json()
        if (append) {
          setResults((prev) => [...prev, ...data.hits])
        } else {
          setResults(data.hits)
        }
        setTotal(data.total_hits)
        setPage(searchPage)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Search failed')
      } finally {
        setLoading(false)
      }
    },
    [selectedTypes, dateFrom, dateTo]
  )

  const handleSearch = (e?: React.FormEvent) => {
    e?.preventDefault()
    if (!query.trim()) return
    setHasSearched(true)
    doSearch(query, 1, false)
  }

  const handleLoadMore = () => {
    doSearch(query, page + 1, true)
  }

  const handleClear = () => {
    setQuery('')
    setSelectedTypes(new Set())
    setDateFrom('')
    setDateTo('')
    setResults([])
    setTotal(0)
    setHasSearched(false)
    setError(null)
  }

  const handleToggleType = (type: string) => {
    setSelectedTypes((prev) => {
      const next = new Set(prev)
      if (next.has(type)) {
        next.delete(type)
      } else {
        next.add(type)
      }
      return next
    })
  }

  /* ── Navigate on card click ──────────────────────────────────────────── */

  const handleCardClick = (hit: SearchHit) => {
    const path = getEntityPath(hit)
    if (path !== '#') {
      navigate(path)
    }
  }

  /* ── Derived ─────────────────────────────────────────────────────────── */

  const filterCount = selectedTypes.size + (dateFrom ? 1 : 0) + (dateTo ? 1 : 0)

  /* ── Render ──────────────────────────────────────────────────────────── */

  return (
    <div className="global-search page-shell">
      {/* ── Page Header ─────────────────────────────────────────────────── */}
      <div className="global-search__header">
        <span className="eyebrow">
          <span className="eyebrow__dot" />
          Search
        </span>
        <h1>Global Search</h1>
      </div>

      {/* ── Search Form ─────────────────────────────────────────────────── */}
      <form onSubmit={handleSearch} className="global-search__form">
        <div className="global-search__input-row">
          <div className="global-search__input-wrapper">
            <Search size={20} className="global-search__input-icon" />
            <input
              type="text"
              className="global-search__input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search across all entities…"
              autoFocus
            />
            {query && (
              <button
                type="button"
                className="global-search__input-clear"
                onClick={() => setQuery('')}
                title="Clear search"
              >
                <X size={16} />
              </button>
            )}
          </div>
          <button
            type="submit"
            className="btn btn-primary global-search__submit"
            disabled={loading || !query.trim()}
          >
            <Search size={18} />
            <span>Search</span>
          </button>
        </div>

        {/* ── Filter Row ────────────────────────────────────────────────── */}
        {/* Mobile: collapsed toggle */}
        <div className="global-search__filter-toggle">
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setFiltersExpanded(!filtersExpanded)}
          >
            <Filter size={16} />
            <span>Filters{filterCount > 0 ? ` (${filterCount})` : ''}</span>
            {filtersExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
          {hasActiveFilters && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={handleClear}>
              Clear all
            </button>
          )}
        </div>

        {/* Desktop/tablet: inline filters */}
        <div className={`global-search__filters ${filtersExpanded ? 'global-search__filters--expanded' : ''}`}>
          {/* Entity type chips */}
          <div className="global-search__filter-group">
            <label className="global-search__filter-label">Entity Types</label>
            <div className="global-search__chips">
              {ENTITY_TYPES.map((et) => {
                const Icon = et.icon
                const active = selectedTypes.has(et.value)
                return (
                  <button
                    key={et.value}
                    type="button"
                    className={`global-search__chip ${active ? 'global-search__chip--active' : ''}`}
                    onClick={() => handleToggleType(et.value)}
                  >
                    <Icon size={14} />
                    <span>{et.label}</span>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Date range */}
          <div className="global-search__filter-group global-search__filter-group--dates">
            <label className="global-search__filter-label">Date From</label>
            <input
              type="date"
              className="input"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
          </div>
          <div className="global-search__filter-group global-search__filter-group--dates">
            <label className="global-search__filter-label">Date To</label>
            <input
              type="date"
              className="input"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
            />
          </div>

          {/* Clear (desktop inline) */}
          {hasActiveFilters && (
            <button
              type="button"
              className="btn btn-ghost btn-sm global-search__filter-clear-inline"
              onClick={handleClear}
            >
              Clear all
            </button>
          )}
        </div>
      </form>

      {/* ── Error ────────────────────────────────────────────────────────── */}
      {error && (
        <div className="global-search__error">
          <X size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* ── Results ──────────────────────────────────────────────────────── */}
      {hasSearched && !error && (
        <div className="global-search__results">
          {/* Results header */}
          <div className="global-search__results-header">
            {results.length > 0 ? (
              <>
                <h2 className="global-search__results-title">
                  Results
                </h2>
                <span className="global-search__results-count">
                  Showing {results.length} of {total.toLocaleString()}
                </span>
              </>
            ) : (
              <h2 className="global-search__results-title">
                No results found
              </h2>
            )}
          </div>

          {/* Empty state */}
          {results.length === 0 && !loading && (
            <div className="global-search__empty">
              <SearchX size={40} />
              <p>No results found for &ldquo;{query}&rdquo;</p>
              <p className="global-search__empty-hint">
                Try broadening your search or adjusting filters.
              </p>
            </div>
          )}

          {/* Result cards */}
          {results.length > 0 && (
            <div className="global-search__list">
              {results.map((hit, index) => (
                <SearchResultCard
                  key={`${hit.entity_type}-${hit.entity_id}-${index}`}
                  hit={hit}
                  onClick={() => handleCardClick(hit)}
                />
              ))}
            </div>
          )}

          {/* Loading indicator */}
          {loading && (
            <div className="global-search__loading">
              <Loader2 size={20} className="global-search__loading-icon" />
              <span>Searching…</span>
            </div>
          )}

          {/* Load More */}
          {results.length > 0 && results.length < total && !loading && (
            <div className="global-search__load-more">
              <button className="btn btn-primary" onClick={handleLoadMore}>
                Load More
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/* ── Result Card ──────────────────────────────────────────────────────────── */

function SearchResultCard({
  hit,
  onClick,
}: {
  hit: SearchHit
  onClick: () => void
}) {
  const Icon = getEntityIcon(hit.entity_type)

  return (
    <button
      type="button"
      className="global-search__card"
      onClick={onClick}
    >
      {/* Entity icon */}
      <div className="global-search__card-icon">
        <Icon size={20} />
      </div>

      <div className="global-search__card-body">
        {/* Top row: entity badge + relevance */}
        <div className="global-search__card-meta">
          <span className="global-search__card-type">
            {getEntityLabel(hit.entity_type)}
          </span>
          {hit.score != null && hit.score > 0 && (
            <span className="global-search__card-score">
              {Math.round(hit.score * 100)}% match
            </span>
          )}
        </div>

        {/* Title — primary link */}
        <h3 className="global-search__card-title">
          {hit.title}
        </h3>

        {/* Description */}
        {hit.description && (
          <p className="global-search__card-desc">
            {hit.description}
          </p>
        )}

        {/* Metadata row: date only, no raw IDs */}
        <div className="global-search__card-footer">
          {hit.created_at && (
            <span className="global-search__card-date">
              {formatRelativeDate(hit.created_at)}
            </span>
          )}
        </div>
      </div>
    </button>
  )
}
