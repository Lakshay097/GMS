import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

interface School {
  id: string
  name: string
  code: string
  status: string
  address?: string
  contact_email?: string
  contact_phone?: string
  created_at: string
  deactivated_at?: string
}

interface SchoolListResponse {
  data: School[]
  pagination: {
    page: number
    page_size: number
    total_count: number
    has_next: boolean
  }
}

export default function SchoolList() {
  const [schools, setSchools] = useState<School[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)

  useEffect(() => {
    fetchSchools()
  }, [page])

  const fetchSchools = async () => {
    try {
      setLoading(true)
      const token = localStorage.getItem('auth_token')
      const response = await fetch(`/api/v1/schools?page=${page}&page_size=50`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })
      
      if (!response.ok) {
        throw new Error('Failed to fetch schools')
      }
      
      const data: SchoolListResponse = await response.json()
      setSchools(data.data)
      setTotal(data.pagination.total_count)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const handleDeactivate = async (schoolId: string) => {
    if (!confirm('Are you sure you want to deactivate this school? This will make all data read-only.')) {
      return
    }

    try {
      const token = localStorage.getItem('auth_token')
      const response = await fetch(`/api/v1/schools/${schoolId}/deactivate`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })
      
      if (!response.ok) {
        throw new Error('Failed to deactivate school')
      }
      
      await fetchSchools()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to deactivate school')
    }
  }

  if (loading) return <div>Loading...</div>
  if (error) return <div>Error: {error}</div>

  return (
    <div className="school-list">
      <div className="header">
        <h1>Schools</h1>
        <Link to="/schools/new" className="btn btn-primary">Create School</Link>
      </div>
      
      <table className="data-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Code</th>
            <th>Status</th>
            <th>Contact Email</th>
            <th>Created</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {schools.map(school => (
            <tr key={school.id}>
              <td>
                <Link to={`/schools/${school.id}`}>{school.name}</Link>
              </td>
              <td>{school.code}</td>
              <td>
                <span className={`status status-${school.status}`}>
                  {school.status}
                </span>
              </td>
              <td>{school.contact_email || '-'}</td>
              <td>{new Date(school.created_at).toLocaleDateString()}</td>
              <td>
                <Link to={`/schools/${school.id}/edit`} className="btn btn-sm">Edit</Link>
                {school.status === 'active' && (
                  <button 
                    onClick={() => handleDeactivate(school.id)}
                    className="btn btn-sm btn-danger"
                  >
                    Deactivate
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      
      <div className="pagination">
        <button 
          onClick={() => setPage(p => Math.max(1, p - 1))}
          disabled={page === 1}
          className="btn btn-sm"
        >
          Previous
        </button>
        <span>Page {page}</span>
        <button 
          onClick={() => setPage(p => p + 1)}
          disabled={page * 50 >= total}
          className="btn btn-sm"
        >
          Next
        </button>
      </div>
    </div>
  )
}