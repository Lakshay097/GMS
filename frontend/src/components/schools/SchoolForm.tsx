import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { apiFetch } from '../../lib/api'

interface SchoolFormData {
  name: string
  code: string
  address?: string
  contact_email?: string
  contact_phone?: string
}

interface School {
  id: string
  name: string
  code: string
  status: string
  address?: string
  contact_email?: string
  contact_phone?: string
}

interface FieldErrors {
  name?: string
  code?: string
  contact_email?: string
}

export default function SchoolForm() {
  const navigate = useNavigate()
  const { id } = useParams()
  const isEdit = !!id
  
  const [formData, setFormData] = useState<SchoolFormData>({
    name: '',
    code: '',
    address: '',
    contact_email: '',
    contact_phone: ''
  })
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})

  useEffect(() => {
    if (!isEdit) return
    const controller = new AbortController()
    const load = async () => {
      try {
        setLoading(true)
        const response = await apiFetch(`/api/v1/schools/${id}`, { signal: controller.signal })
        
        if (!response.ok) {
          throw new Error('Failed to fetch school')
        }
        
        const school: School = await response.json()
        setFormData({
          name: school.name,
          code: school.code,
          address: school.address || '',
          contact_email: school.contact_email || '',
          contact_phone: school.contact_phone || ''
        })
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setError(err instanceof Error ? err.message : 'An error occurred')
      } finally {
        setLoading(false)
      }
    }
    load()
    return () => controller.abort()
  }, [id, isEdit])

  const validateField = (name: string, value: string): string | null => {
    switch (name) {
      case 'name':
        if (!value.trim()) return 'Name is required'
        if (value.length < 2) return 'Name must be at least 2 characters'
        return null
      case 'code':
        if (!value.trim()) return 'Code is required'
        if (!/^[A-Z]{3}-[A-Z]{3}$/.test(value)) {
          return 'Code must be in format XXX-XXX (e.g., GUR-JAI)'
        }
        return null
      case 'contact_email':
        if (value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
          return 'Please enter a valid email address'
        }
        return null
      default:
        return null
    }
  }

  const validateForm = (): boolean => {
    const errors: FieldErrors = {}
    let isValid = true

    // Validate all fields
    const nameError = validateField('name', formData.name)
    if (nameError) {
      errors.name = nameError
      isValid = false
    }

    const codeError = validateField('code', formData.code)
    if (codeError) {
      errors.code = codeError
      isValid = false
    }

    const emailError = validateField('contact_email', formData.contact_email || '')
    if (emailError) {
      errors.contact_email = emailError
      isValid = false
    }

    setFieldErrors(errors)
    return isValid
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target
    setFormData(prev => ({ ...prev, [name]: value }))
    
    // Clear field error when user starts typing
    if (fieldErrors[name as keyof FieldErrors]) {
      setFieldErrors(prev => ({ ...prev, [name]: undefined }))
    }
  }

  const handleBlur = (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target
    
    const error = validateField(name, value)
    if (error) {
      setFieldErrors(prev => ({ ...prev, [name]: error }))
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    
    // Validate form
    if (!validateForm()) {
      return
    }
    
    try {
      setSubmitting(true)
      const url = isEdit ? `/api/v1/schools/${id}` : '/api/v1/schools'
      const method = isEdit ? 'PATCH' : 'POST'
      
      const response = await apiFetch(url, {
        method,
        body: JSON.stringify(formData)
      })
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => null)
        throw new Error(errorData?.error?.message || 'Failed to save school')
      }
      
      navigate('/schools')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save school')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading && isEdit) return <div className="loading-state">Loading school…</div>

  return (
    <div className="form-page page-shell">
      <div className="form-header">
        <button 
          onClick={() => navigate('/schools')} 
          className="btn btn-ghost"
        >
          ← Schools
        </button>
        <h1>{isEdit ? 'Edit School' : 'Create School'}</h1>
      </div>
      
      {error && (
        <div className="error-banner">
          {error}
        </div>
      )}
      
      <form onSubmit={handleSubmit} className="form-card">
        <div className="form-group">
          <label htmlFor="name">Name *</label>
          <input
            type="text"
            id="name"
            name="name"
            value={formData.name}
            onChange={handleChange}
            onBlur={handleBlur}
            className={`form-input ${fieldErrors.name ? 'form-input--error' : ''}`}
            placeholder="Enter school name"
          />
          {fieldErrors.name && (
            <span className="form-error">{fieldErrors.name}</span>
          )}
        </div>
        
        <div className="form-group">
          <label htmlFor="code">Code *</label>
          <div className="input-with-icon">
            <input
              type="text"
              id="code"
              name="code"
              value={formData.code}
              onChange={handleChange}
              onBlur={handleBlur}
              disabled={isEdit}
              className={`form-input ${fieldErrors.code ? 'form-input--error' : ''} ${isEdit ? 'form-input--disabled' : ''}`}
              placeholder="GUR-JAI"
            />
            {isEdit && (
              <span className="input-icon input-icon--locked" title="Code cannot be changed after creation">
                🔒
              </span>
            )}
          </div>
          {fieldErrors.code && (
            <span className="form-error">{fieldErrors.code}</span>
          )}
          {isEdit && (
            <span className="form-hint">Code cannot be changed after creation</span>
          )}
        </div>
        
        <div className="form-group">
          <label htmlFor="address">Address</label>
          <textarea
            id="address"
            name="address"
            value={formData.address}
            onChange={handleChange}
            rows={3}
            className="form-input"
            placeholder="Enter school address"
          />
        </div>
        
        <div className="form-group">
          <label htmlFor="contact_email">Contact Email</label>
          <input
            type="email"
            id="contact_email"
            name="contact_email"
            value={formData.contact_email}
            onChange={handleChange}
            onBlur={handleBlur}
            className={`form-input ${fieldErrors.contact_email ? 'form-input--error' : ''}`}
            placeholder="email@example.com"
          />
          {fieldErrors.contact_email && (
            <span className="form-error">{fieldErrors.contact_email}</span>
          )}
        </div>
        
        <div className="form-group">
          <label htmlFor="contact_phone">Contact Phone</label>
          <input
            type="tel"
            id="contact_phone"
            name="contact_phone"
            value={formData.contact_phone}
            onChange={handleChange}
            className="form-input"
            placeholder="+91 98765 43210"
          />
        </div>
        
        <div className="form-actions">
          <button 
            type="button" 
            onClick={() => navigate('/schools')} 
            className="btn btn-secondary"
            disabled={submitting}
          >
            Cancel
          </button>
          <button 
            type="submit" 
            className="btn btn-primary" 
            disabled={submitting}
          >
            {submitting ? (
              <>
                <span className="spinner">⏳</span>
                Saving…
              </>
            ) : (
              'Save School'
            )}
          </button>
        </div>
      </form>
    </div>
  )
}