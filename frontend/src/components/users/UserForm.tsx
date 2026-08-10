import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

interface UserFormData {
  neon_auth_user_id: string
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
  neon_auth_user_id: string
  email: string
  full_name: string
  school_id?: string
  department_id?: string
  status: string
  roles: string[]
  mfa_enabled: boolean
  phone?: string
  employee_id?: string
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
    neon_auth_user_id: '',
    email: '',
    full_name: '',
    school_id: '',
    department_id: '',
    roles: [],
    phone: '',
    employee_id: ''
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (isEdit) {
      fetchUser()
    }
  }, [id, isEdit])

  const fetchUser = async () => {
    try {
      setLoading(true)
      const token = localStorage.getItem('auth_token')
      const response = await fetch(`/api/v1/users/${id}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })
      
      if (!response.ok) {
        throw new Error('Failed to fetch user')
      }
      
      const user: User = await response.json()
      setFormData({
        neon_auth_user_id: user.neon_auth_user_id,
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    
    if (formData.roles.length === 0) {
      setError('At least one role is required')
      return
    }
    
    try {
      setLoading(true)
      const token = localStorage.getItem('auth_token')
      
      const url = isEdit ? `/api/v1/users/${id}` : '/api/v1/users'
      const method = isEdit ? 'PATCH' : 'POST'
      
      const response = await fetch(url, {
        method,
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
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
      setLoading(false)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target
    setFormData(prev => ({ ...prev, [name]: value }))
  }

  const handleRoleToggle = (role: string) => {
    setFormData(prev => ({
      ...prev,
      roles: prev.roles.includes(role)
        ? prev.roles.filter(r => r !== role)
        : [...prev.roles, role]
    }))
  }

  if (loading && isEdit) return <div>Loading...</div>

  return (
    <div className="user-form">
      <div className="header">
        <h1>{isEdit ? 'Edit User' : 'Create User'}</h1>
        <button onClick={() => navigate('/users')} className="btn">Back</button>
      </div>
      
      {error && <div className="error">{error}</div>}
      
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="neon_auth_user_id">Neon Auth User ID *</label>
          <input
            type="text"
            id="neon_auth_user_id"
            name="neon_auth_user_id"
            value={formData.neon_auth_user_id}
            onChange={handleChange}
            required
            disabled={isEdit}
          />
        </div>
        
        <div className="form-group">
          <label htmlFor="email">Email *</label>
          <input
            type="email"
            id="email"
            name="email"
            value={formData.email}
            onChange={handleChange}
            required
            disabled={isEdit}
          />
        </div>
        
        <div className="form-group">
          <label htmlFor="full_name">Full Name *</label>
          <input
            type="text"
            id="full_name"
            name="full_name"
            value={formData.full_name}
            onChange={handleChange}
            required
          />
        </div>
        
        <div className="form-group">
          <label htmlFor="school_id">School ID</label>
          <input
            type="text"
            id="school_id"
            name="school_id"
            value={formData.school_id}
            onChange={handleChange}
          />
        </div>
        
        <div className="form-group">
          <label htmlFor="department_id">Department ID</label>
          <input
            type="text"
            id="department_id"
            name="department_id"
            value={formData.department_id}
            onChange={handleChange}
          />
        </div>
        
        <div className="form-group">
          <label>Roles * (at least one)</label>
          <div className="checkbox-group">
            {ROLE_OPTIONS.map(role => (
              <label key={role.value} className="checkbox-label">
                <input
                  type="checkbox"
                  checked={formData.roles.includes(role.value)}
                  onChange={() => handleRoleToggle(role.value)}
                />
                {role.label}
              </label>
            ))}
          </div>
        </div>
        
        <div className="form-group">
          <label htmlFor="phone">Phone</label>
          <input
            type="tel"
            id="phone"
            name="phone"
            value={formData.phone}
            onChange={handleChange}
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
          />
        </div>
        
        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? 'Saving...' : (isEdit ? 'Update' : 'Create')}
          </button>
          <button type="button" onClick={() => navigate('/users')} className="btn">
            Cancel
          </button>
        </div>
      </form>
    </div>
  )
}