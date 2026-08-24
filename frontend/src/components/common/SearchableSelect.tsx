import { useState, useRef, useEffect } from 'react'

interface SearchableSelectOption {
  value: string
  label: string
  sublabel?: string
}

interface SearchableSelectProps {
  id: string
  name: string
  value: string
  onChange: (value: string) => void
  options: SearchableSelectOption[]
  placeholder?: string
  disabled?: boolean
  required?: boolean
  loading?: boolean
  onSearch?: (query: string) => void
  useServerSearch?: boolean // Enable server-side search for large datasets
  unsetLabel?: string // Display text for unset optional relation
}

export default function SearchableSelect({
  id,
  name,
  value,
  onChange,
  options,
  placeholder = 'Select...',
  disabled = false,
  required = false,
  loading = false,
  onSearch,
  useServerSearch = false,
  unsetLabel
}: SearchableSelectProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const dropdownRef = useRef<HTMLDivElement>(null)
  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout>>()

  const selectedOption = options.find(opt => opt.value === value)

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  // Handle search with debouncing for server-side search
  const handleSearchInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const query = e.target.value
    setSearchQuery(query)
    
    if (useServerSearch && onSearch) {
      // Clear previous timeout
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current)
      }
      
      // Debounce server search (300ms)
      searchTimeoutRef.current = setTimeout(() => {
        onSearch(query)
      }, 300)
    }
  }

  // Filter options based on search query (client-side)
  const filteredOptions = options.filter(option => {
    if (!searchQuery) return true
    
    const searchLower = searchQuery.toLowerCase()
    return (
      option.label.toLowerCase().includes(searchLower) ||
      (option.sublabel && option.sublabel.toLowerCase().includes(searchLower))
    )
  })

  const handleSelect = (optionValue: string) => {
    onChange(optionValue)
    setIsOpen(false)
    setSearchQuery('')
  }

  const handleClear = () => {
    onChange('')
    setIsOpen(false)
    setSearchQuery('')
  }

  const displayValue = selectedOption ? (
    <div className="select-display">
      <span className="select-display__label">{selectedOption.label}</span>
      {selectedOption.sublabel && (
        <span className="select-display__sublabel">{selectedOption.sublabel}</span>
      )}
    </div>
  ) : (
    <span className="select-display__placeholder">{value ? 'Unknown selection' : (unsetLabel || placeholder)}</span>
  )

  return (
    <div className="searchable-select" ref={dropdownRef}>
      <div
        className={`searchable-select__trigger ${isOpen ? 'searchable-select__trigger--open' : ''} ${
          disabled ? 'searchable-select__trigger--disabled' : ''
        }`}
        onClick={() => !disabled && setIsOpen(!isOpen)}
        id={id}
        data-name={name}
        data-required={required}
      >
        <div className="searchable-select__value">
          {displayValue}
        </div>
        {!disabled && (
          <div className="searchable-select__actions">
            {value && !required && (
              <button
                type="button"
                className="searchable-select__clear"
                onClick={(e) => {
                  e.stopPropagation()
                  handleClear()
                }}
                title="Clear selection"
              >
                ×
              </button>
            )}
            <span className="searchable-select__chevron">▼</span>
          </div>
        )}
      </div>

      {isOpen && !disabled && (
        <div className="searchable-select__dropdown">
          <div className="searchable-select__search">
            <input
              type="text"
              value={searchQuery}
              onChange={handleSearchInputChange}
              placeholder={useServerSearch ? "Search..." : "Filter..."}
              className="searchable-select__search-input"
              autoFocus
            />
          </div>
          <div className="searchable-select__options">
            {loading ? (
              <div className="searchable-select__loading">Loading...</div>
            ) : filteredOptions.length === 0 ? (
              <div className="searchable-select__no-results">
                {searchQuery ? "No results found" : (unsetLabel || "No options available")}
              </div>
            ) : (
              filteredOptions.map(option => (
                <div
                  key={option.value}
                  className={`searchable-select__option ${
                    option.value === value ? 'searchable-select__option--selected' : ''
                  }`}
                  onClick={() => handleSelect(option.value)}
                >
                  <div className="searchable-select__option-label">{option.label}</div>
                  {option.sublabel && (
                    <div className="searchable-select__option-sublabel">{option.sublabel}</div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
