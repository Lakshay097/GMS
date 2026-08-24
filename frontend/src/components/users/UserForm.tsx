import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import SearchableSelect from '../common/SearchableSelect'

interface UserFormData {
  clerk_user_id: string
  email: string
  full_name: string
  school_id?: string
  department_id?: string
  roles: string[]
  phone?: string
  employee_id?: string
}

interface User {
  id: string
  clerk_user_id: string
  email: string
  full_name: string
  school_id?: string
  department_id?: string
  requested_department_id?: string
  requested_department_name?: string
  department_request_status?: 'none' | 'pending' | 'approved' | 'rejected'
  status: string
  roles: string[]
  mfa_enabled: boolean
  phone?: string
  employee_id?: string
}

interface School {
  id: string
  name: string
  code: string
}

interface Department {
  id: string
  name: string
  code: string
  school_id: string
}

interface FieldErrors {
  clerk_user_id?: string
  email?: string
  full_name?: string
  school_id?: string
  roles?: string
}

const ROLE_OPTIONS = [
  { value: 'superadmin', label: 'SuperAdmin' },
  { value: 'admin', label: 'Admin' },
  { value: 'checker', label: 'Checker' },
  { value: 'auditor', label: 'Auditor' },
  { value: 'viewer', label: 'Viewer' }
]

export default function UserForm() {
  const navigate = useNavigate()
  const { id } = useParams()
  const isEdit = !!id
  
  const [formData, setFormData] = useState<UserFormData>({
    clerk_user_id: '',
    email: '',
    full_name: '',
    school_id: '',
    department_id: '',
    roles: [],
    phone: '',
    employee_id: ''
  })
  const [userData, setUserData] = useState<User | null>(null)
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [schools, setSchools] = useState<School[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [schoolsLoading, setSchoolsLoading] = useState(false)
  const [departmentsLoading, setDepartmentsLoading] = useState(false)

  useEffect(() => {
    fetchSchools()
    fetchDepartments()
    if (isEdit) {
      fetchUser()
    }
  }, [id, isEdit])

  const fetchSchools = async () => {
    try {
      setSchoolsLoading(true)
      const response = await apiFetch('/api/v1/schools?page=1&page_size=200')
      if (response.ok) {
        const data = await response.json()
        setSchools(data.data || [])
      }
    } catch (err) {
      console.error('Failed to fetch schools:', err)
      setSchools([])
    } finally {
      setSchoolsLoading(false)
    }
  }

  const fetchDepartments = async (schoolId?: string) => {
    try {
      setDepartmentsLoading(true)
      let url = '/api/v1/departments?page=1&page_size=200'
      if (schoolId) {
        url += `&school_id=${schoolId}`
      }
      const response = await apiFetch(url)
      if (response.ok) {
        const data = await response.json()
        setDepartments(data.data || [])
      }
    } catch (err) {
      console.error('Failed to fetch departments:', err)
      setDepartments([])
    } finally {
      setDepartmentsLoading(false)
    }
  }

  const fetchUser = async () => {
    try {
      setLoading(true)
      const response = await apiFetch(`/api/v1/users/${id}`)
      
      if (!response.ok) {
        throw new Error('Failed to fetch user')
      }
      
      const user: User = await response.json()
      setUserData(user)
      setFormData({
        clerk_user_id: user.clerk_user_id,
        email: user.email,
        full_name: user.full_name,
        school_id: user.school_id || '',
        department_id: user.department_id || '',
        roles: user.roles,
        phone: user.phone || '',
        employee_id: user.employee_id || ''
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const validateField = (name: string, value: any): string | null => {
    switch (name) {
      case 'clerk_user_id':
        // NOTE: This field's requirement depends on auth provisioning flow
        // Currently marked as required, but should be confirmed with auth owner
        // If users are created via invite first, this should be optional at creation
        if (!value.trim()) return 'Clerk User ID is required'
        return null
      case 'email':
        if (!value.trim()) return 'Email is required'
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
          return 'Please enter a valid email address'
        }
        return null
      case 'full_name':
        if (!value.trim()) return 'Full Name is required'
        if (value.length < 2) return 'Full Name must be at least 2 characters'
        return null
      case 'roles':
        if (!Array.isArray(value) || value.length === 0) {
          return 'At least one role is required'
        }
        return null
      default:
        return null
    }
  }

  const validateForm = (): boolean => {
    const errors: FieldErrors = {}
    let isValid = true

    const neonAuthError = validateField('clerk_user_id', formData.clerk_user_id)
    if (neonAuthError) {
      errors.clerk_user_id = neonAuthError
      isValid = false
    }

    const emailError = validateField('email', formData.email)
    if (emailError) {
      errors.email = emailError
      isValid = false
    }

    const nameError = validateField('full_name', formData.full_name)
    if (nameError) {
      errors.full_name = nameError
      isValid = false
    }

    const rolesError = validateField('roles', formData.roles)
    if (rolesError) {
      errors.roles = rolesError
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

  const handleSchoolChange = (schoolId: string) => {
    setFormData(prev => ({ ...prev, school_id: schoolId, department_id: '' }))
    // Clear department when school changes
    if (schoolId) {
      fetchDepartments(schoolId)
    } else {
      setDepartments([])
    }
    
    if (fieldErrors.school_id) {
      setFieldErrors(prev => ({ ...prev, school_id: undefined }))
    }
  }

  const handleRoleToggle = (role: string) => {
    setFormData(prev => {
      const newRoles = prev.roles.includes(role)
        ? prev.roles.filter(r => r !== role)
        : [...prev.roles, role]
      
      // Clear roles error if at least one role is selected
      if (newRoles.length > 0 && fieldErrors.roles) {
        setFieldErrors(prev => ({ ...prev, roles: undefined }))
      }
      
      return { ...prev, roles: newRoles }
    })
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
      
      const url = isEdit ? `/api/v1/users/${id}` : '/api/v1/users'
      const method = isEdit ? 'PATCH' : 'POST'
      
      const response = await apiFetch(url, {
        method,
        body: JSON.stringify(formData)
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error?.message || 'Failed to save user')
      }
      
      navigate('/users')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save user')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading && isEdit) return <div className="loading-state">Loading user…</div>

  const schoolOptions = schools.map(school => ({
    value: school.id,
    label: school.name,
    sublabel: school.code
  }))

  const departmentOptions = departments
    .filter(dept => !formData.school_id || dept.school_id === formData.school_id)
    .map(dept => ({
      value: dept.id,
      label: dept.name,
      sublabel: dept.code
    }))

  return (
    <div className="form-page page-shell">
      <div className="form-header">
        <button 
          onClick={() => navigate('/users')} 
          className="btn btn-ghost"
        >
          ← Users
        </button>
        <h1>{isEdit ? 'Edit User' : 'Create User'}</h1>
      </div>
      
      {error && (
        <div className="error-banner">
          {error}
        </div>
      )}
      
      <form onSubmit={handleSubmit} className="form-card">
        <div className="form-group">
          <label htmlFor="clerk_user_id">Clerk User ID *</label>
          <div className="input-with-icon">
            <input
              type="text"
              id="clerk_user_id"
              name="clerk_user_id"
              value={formData.clerk_user_id}
              onChange={handleChange}
              onBlur={handleBlur}
              disabled={isEdit}
              className={`form-input ${fieldErrors.clerk_user_id ? 'form-input--error' : ''} ${isEdit ? 'form-input--disabled' : ''}`}
              placeholder="Enter Clerk User ID"
            />
            {isEdit && (
              <span className="input-icon input-icon--locked" title="Cannot be changed after creation">
                🔒
              </span>
            )}
          </div>
          {fieldErrors.clerk_user_id && (
            <span className="form-error">{fieldErrors.clerk_user_id}</span>
          )}
          {isEdit && (
            <span className="form-hint">Cannot be changed after creation</span>
          )}
        </div>
        
        <div className="form-group">
          <label htmlFor="email">Email *</label>
          <div className="input-with-icon">
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              onBlur={handleBlur}
              disabled={isEdit}
              className={`form-input ${fieldErrors.email ? 'form-input--error' : ''} ${isEdit ? 'form-input--disabled' : ''}`}
              placeholder="email@example.com"
            />
            {isEdit && (
              <span className="input-icon input-icon--locked" title="Email cannot be changed after creation">
                🔒
              </span>
            )}
          </div>
          {fieldErrors.email && (
            <span className="form-error">{fieldErrors.email}</span>
          )}
          {isEdit && (
            <span className="form-hint">Email cannot be changed after creation</span>
          )}
        </div>
        
        <div className="form-group">
          <label htmlFor="full_name">Full Name *</label>
          <input
            type="text"
            id="full_name"
            name="full_name"
            value={formData.full_name}
            onChange={handleChange}
            onBlur={handleBlur}
            className={`form-input ${fieldErrors.full_name ? 'form-input--error' : ''}`}
            placeholder="Enter full name"
          />
          {fieldErrors.full_name && (
            <span className="form-error">{fieldErrors.full_name}</span>
          )}
        </div>
        
        <div className="form-group">
          <label htmlFor="school_id">School</label>
          <SearchableSelect
            id="school_id"
            name="school_id"
            value={formData.school_id || ''}
            onChange={handleSchoolChange}
            options={schoolOptions}
            placeholder="Select school (optional)"
            loading={schoolsLoading}
          />
        </div>
        
        <div className="form-group">
          <label htmlFor="department_id">Department</label>
          <SearchableSelect
            id="department_id"
            name="department_id"
            value={formData.department_id || ''}
            onChange={(value) => {
              setFormData(prev => ({ ...prev, department_id: value }))
            }}
            options={departmentOptions}
            placeholder={formData.school_id ? "Select department (optional)" : "Select a school first"}
            loading={departmentsLoading}
            disabled={!formData.school_id}
          />
          {!formData.school_id && (
            <span className="form-hint">Select a school to see available departments</span>
          )}
          {isEdit && userData?.department_request_status === 'pending' && userData.requested_department_name && (
            <div className="form-info">
              <span className="form-info__label">Pending approval:</span>
              <span className="form-info__value">{userData.requested_department_name}</span>
            </div>
          )}
        </div>
        
        <div className="form-group">
          <label>Roles *</label>
          <div className="checkbox-group">
            {ROLE_OPTIONS.map((role, index) => (
              <label key={`role-${index}`} className="checkbox-label">
                <input
                  type="checkbox"
                  checked={formData.roles.includes(role.value)}
                  onChange={() => handleRoleToggle(role.value)}
                />
                <span>{role.label}</span>
              </label>
            ))}
          </div>
          {fieldErrors.roles && (
            <span className="form-error">{fieldErrors.roles}</span>
          )}
        </div>
        
        <div className="form-group">
          <label htmlFor="phone">Phone</label>
          <input
            type="tel"
            id="phone"
            name="phone"
            value={formData.phone}
            onChange={handleChange}
            className="form-input"
            placeholder="+91 98765 43210"
          />
        </div>
        
        <div className="form-group">
          <label htmlFor="employee_id">Employee ID</label>
          <input
            type="text"
            id="employee_id"
            name="employee_id"
            value={formData.employee_id}
            onChange={handleChange}
            className="form-input"
            placeholder="Enter employee ID"
          />
        </div>
        
        <div className="form-actions">
          <button 
            type="button" 
            onClick={() => navigate('/users')} 
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
              'Save User'
            )}
          </button>
        </div>
      </form>
    </div>
  )
}