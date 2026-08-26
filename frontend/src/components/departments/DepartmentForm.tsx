import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import { useSchoolContext } from '../../contexts/SchoolContext'
import SearchableSelect from '../common/SearchableSelect'

interface DepartmentFormData {
  school_id: string
  name: string
  code: string
  description?: string
  head_user_id?: string
  auto_accept_requests: boolean
}

interface Department {
  id: string
  school_id: string
  name: string
  code: string
  status: string
  description?: string
  head_user_id?: string
  auto_accept_requests: boolean
}


interface User {
  id: string
  full_name: string
  email: string
}

interface FieldErrors {
  school_id?: string
  name?: string
  code?: string
}

export default function DepartmentForm() {
  const navigate = useNavigate()
  const { id } = useParams()
  const isEdit = !!id
  
  const [formData, setFormData] = useState<DepartmentFormData>({
    school_id: '',
    name: '',
    code: '',
    description: '',
    head_user_id: '',
    auto_accept_requests: false
  })
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  // ── Active school from global context ──────────────────────────────────
  const { activeSchoolId, activeSchool } = useSchoolContext()

  const [users, setUsers] = useState<User[]>([])
  const [usersLoading, setUsersLoading] = useState(false)

  // Auto-sync school from global context (updates if SuperAdmin switches school)
  useEffect(() => {
    if (activeSchoolId && activeSchoolId !== formData.school_id) {
      setFormData(prev => ({ ...prev, school_id: activeSchoolId }))
    }
  }, [activeSchoolId])

  const fetchUsers = async () => {
    try {
      setUsersLoading(true)
      const response = await apiFetch('/api/v1/users?page=1&page_size=200')
      if (response.ok) {
        const data = await response.json()
        setUsers(data.data || [])
      } else {
        console.warn('Failed to fetch users:', response.status)
        // Set empty users array to allow form to work without department head selection
        setUsers([])
      }
    } catch (err) {
      console.error('Failed to fetch users:', err)
      // Set empty users array to allow form to work without department head selection
      setUsers([])
    } finally {
      setUsersLoading(false)
    }
  }

  const fetchDepartment = async () => {
    try {
      setLoading(true)
      const response = await apiFetch(`/api/v1/departments/${id}`)
      
      if (!response.ok) {
        throw new Error('Failed to fetch department')
      }
      
      const dept: Department = await response.json()
      setFormData({
        school_id: dept.school_id,
        name: dept.name,
        code: dept.code,
        description: dept.description || '',
        head_user_id: dept.head_user_id || '',
        auto_accept_requests: dept.auto_accept_requests || false
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchUsers()
    if (isEdit) {
      fetchDepartment()
    }
  }, [id, isEdit])

  const validateField = (name: string, value: string): string | null => {
    switch (name) {
      case 'school_id':
        if (!value.trim()) return 'School is required'
        return null
      case 'name':
        if (!value.trim()) return 'Name is required'
        if (value.length < 2) return 'Name must be at least 2 characters'
        return null
      case 'code':
        if (!value.trim()) return 'Code is required'
        return null
      default:
        return null
    }
  }

  const validateForm = (): boolean => {
    const errors: FieldErrors = {}
    let isValid = true

    const schoolIdError = validateField('school_id', formData.school_id)
    if (schoolIdError) {
      errors.school_id = schoolIdError
      isValid = false
    }

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
      const url = isEdit ? `/api/v1/departments/${id}` : '/api/v1/departments'
      const method = isEdit ? 'PATCH' : 'POST'
      
      const response = await apiFetch(url, {
        method,
        body: JSON.stringify(formData)
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error?.message || 'Failed to save department')
      }
      
      navigate('/departments')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save department')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading && isEdit) return <div className="loading-state">Loading department…</div>

  const userOptions = users.map(user => ({
    value: user.id,
    label: user.full_name,
    sublabel: user.email
  }))

  return (
    <div className="form-page page-shell">
      <div className="form-header">
        <button 
          onClick={() => navigate('/departments')} 
          className="btn btn-ghost"
        >
          ← Departments
        </button>
        <h1>{isEdit ? 'Edit Department' : 'Create Department'}</h1>
      </div>
      
      {error && (
        <div className="error-banner">
          {error}
        </div>
      )}
      
      <form onSubmit={handleSubmit} className="form-card">
        {/* School (auto-set from global context, no manual picker) */}
        {formData.school_id && (
          <div className="form-group">
            <label>School</label>
            <input type="hidden" name="school_id" value={formData.school_id} />
            <div style={{
              padding: '8px 12px', background: 'var(--ink-800)', borderRadius: 8,
              color: 'var(--ink-200)', fontSize: 'var(--text-sm)', fontWeight: 500,
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <span style={{ opacity: 0.5 }}>🏫</span>
              {activeSchool?.name || 'Loading…'}
              {isEdit && <span style={{ marginLeft: 8, fontSize: 'var(--text-xs)', opacity: 0.6 }}>🔒</span>}
            </div>
          </div>
        )}
        
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
            placeholder="Enter department name"
          />
          {fieldErrors.name && (
            <span className="form-error">{fieldErrors.name}</span>
          )}
        </div>
        
        <div className="form-group">
          <label htmlFor="code">Code *</label>
          <input
            type="text"
            id="code"
            name="code"
            value={formData.code}
            onChange={handleChange}
            onBlur={handleBlur}
            className={`form-input ${fieldErrors.code ? 'form-input--error' : ''}`}
            placeholder="Enter department code"
          />
          {fieldErrors.code && (
            <span className="form-error">{fieldErrors.code}</span>
          )}
        </div>
        
        <div className="form-group">
          <label htmlFor="description">Description</label>
          <textarea
            id="description"
            name="description"
            value={formData.description}
            onChange={handleChange}
            rows={3}
            className="form-input"
            placeholder="Enter department description"
          />
        </div>
        
        <div className="form-group">
          <label htmlFor="head_user_id">Department Head</label>
          <SearchableSelect
            id="head_user_id"
            name="head_user_id"
            value={formData.head_user_id || ''}
            onChange={(value) => setFormData(prev => ({ ...prev, head_user_id: value }))}
            options={userOptions}
            unsetLabel="No Department Head assigned"
            placeholder="Select department head (optional)"
            loading={usersLoading}
          />
          {users.length === 0 && !usersLoading && (
            <span className="form-hint">User list unavailable. You can still save the department without assigning a head.</span>
          )}
        </div>

        <div className="form-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              name="auto_accept_requests"
              checked={formData.auto_accept_requests}
              onChange={(e) => setFormData(prev => ({ ...prev, auto_accept_requests: e.target.checked }))}
            />
            <span>Auto-accept join requests</span>
          </label>
          <span className="form-hint">When enabled, users requesting to join this department will be automatically approved without manual review.</span>
        </div>
        
        <div className="form-actions">
          <button 
            type="button" 
            onClick={() => navigate('/departments')} 
            className="btn btn-secondary"
            disabled={submitting}
          >
            Cancel
          </button>
          <button 
            type="submit" 
            className="btn btn-gold" 
            disabled={submitting}
          >
            {submitting ? (
              <>
                <span className="spinner">⏳</span>
                Saving…
              </>
            ) : (
              'Save Department'
            )}
          </button>
        </div>
      </form>
    </div>
  )
}