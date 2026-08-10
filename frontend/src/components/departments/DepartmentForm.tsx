import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

interface DepartmentFormData {
  school_id: string
  name: string
  code: string
  description?: string
  head_user_id?: string
}

interface Department {
  id: string
  school_id: string
  name: string
  code: string
  status: string
  description?: string
  head_user_id?: string
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
    head_user_id: ''
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (isEdit) {
      fetchDepartment()
    }
  }, [id, isEdit])

  const fetchDepartment = async () => {
    try {
      setLoading(true)
      const token = localStorage.getItem('auth_token')
      const response = await fetch(`/api/v1/departments/${id}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })
      
      if (!response.ok) {
        throw new Error('Failed to fetch department')
      }
      
      const dept: Department = await response.json()
      setFormData({
        school_id: dept.school_id,
        name: dept.name,
        code: dept.code,
        description: dept.description || '',
        head_user_id: dept.head_user_id || ''
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
    
    try {
      setLoading(true)
      const token = localStorage.getItem('auth_token')
      
      const url = isEdit ? `/api/v1/departments/${id}` : '/api/v1/departments'
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
        throw new Error(errorData.error?.message || 'Failed to save department')
      }
      
      navigate('/departments')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save department')
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target
    setFormData(prev => ({ ...prev, [name]: value }))
  }

  if (loading && isEdit) return <div>Loading...</div>

  return (
    <div className="department-form">
      <div className="header">
        <h1>{isEdit ? 'Edit Department' : 'Create Department'}</h1>
        <button onClick={() => navigate('/departments')} className="btn">Back</button>
      </div>
      
      {error && <div className="error">{error}</div>}
      
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="school_id">School ID *</label>
          <input
            type="text"
            id="school_id"
            name="school_id"
            value={formData.school_id}
            onChange={handleChange}
            required
            disabled={isEdit} // School cannot be changed
          />
        </div>
        
        <div className="form-group">
          <label htmlFor="name">Name *</label>
          <input
            type="text"
            id="name"
            name="name"
            value={formData.name}
            onChange={handleChange}
            required
          />
        </div>
        
        <div className="form-group">
          <label htmlFor="code">Code *</label>
          <input
            type="text"
            id="code"
            name="code"
            value={formData.code}
            onChange={handleChange}
            required
          />
        </div>
        
        <div className="form-group">
          <label htmlFor="description">Description</label>
          <textarea
            id="description"
            name="description"
            value={formData.description}
            onChange={handleChange}
            rows={3}
          />
        </div>
        
        <div className="form-group">
          <label htmlFor="head_user_id">Department Head User ID</label>
          <input
            type="text"
            id="head_user_id"
            name="head_user_id"
            value={formData.head_user_id}
            onChange={handleChange}
          />
        </div>
        
        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? 'Saving...' : (isEdit ? 'Update' : 'Create')}
          </button>
          <button type="button" onClick={() => navigate('/departments')} className="btn">
            Cancel
          </button>
        </div>
      </form>
    </div>
  )
}