import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

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
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (isEdit) {
      fetchSchool()
    }
  }, [id, isEdit])

  const fetchSchool = async () => {
    try {
      setLoading(true)
      const token = localStorage.getItem('auth_token')
      const response = await fetch(`/api/v1/schools/${id}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })
      
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
      
      const url = isEdit ? `/api/v1/schools/${id}` : '/api/v1/schools'
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
        throw new Error(errorData.error?.message || 'Failed to save school')
      }
      
      navigate('/schools')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save school')
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
    <div className="school-form">
      <div className="header">
        <h1>{isEdit ? 'Edit School' : 'Create School'}</h1>
        <button onClick={() => navigate('/schools')} className="btn">Back</button>
      </div>
      
      {error && <div className="error">{error}</div>}
      
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="name">Name *</label>
          <input
            type="text"
            id="name"
            name="name"
            value={formData.name}
            onChange={handleChange}
            required
            disabled={isEdit && false} // Name can be changed on edit
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
            disabled={isEdit} // Code cannot be changed
          />
        </div>
        
        <div className="form-group">
          <label htmlFor="address">Address</label>
          <textarea
            id="address"
            name="address"
            value={formData.address}
            onChange={handleChange}
            rows={3}
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
          />
        </div>
        
        <div className="form-group">
          <label htmlFor="contact_phone">Contact Phone</label>
          <input
            type="tel"
            id="contact_phone"
            name="contact_phone"
            value={formData.contact_phone}
            onChange={handleChange}
          />
        </div>
        
        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? 'Saving...' : (isEdit ? 'Update' : 'Create')}
          </button>
          <button type="button" onClick={() => navigate('/schools')} className="btn">
            Cancel
          </button>
        </div>
      </form>
    </div>
  )
}