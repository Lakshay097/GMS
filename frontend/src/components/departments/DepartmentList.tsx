import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

interface Department {
  id: string
  school_id: string
  name: string
  code: string
  status: string
  description?: string
  head_user_id?: string
  created_at: string
  archived_at?: string
}

interface DepartmentListResponse {
  data: Department[]
  pagination: {
    page: number
    page_size: number
    total_count: number
    has_next: boolean
  }
}

export default function DepartmentList() {
  const [departments, setDepartments] = useState<Department[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)

  useEffect(() => {
    fetchDepartments()
  }, [page])

  const fetchDepartments = async () => {
    try {
      setLoading(true)
      const token = localStorage.getItem('auth_token')
      const response = await fetch(`/api/v1/departments?page=${page}&page_size=50`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })
      
      if (!response.ok) {
        throw new Error('Failed to fetch departments')
      }
      
      const data: DepartmentListResponse = await response.json()
      setDepartments(data.data)
      setTotal(data.pagination.total_count)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const handleArchive = async (departmentId: string) => {
    if (!confirm('Are you sure you want to archive this department? This will prevent any future assignments.')) {
      return
    }

    try {
      const token = localStorage.getItem('auth_token')
      const response = await fetch(`/api/v1/departments/${departmentId}/archive`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error?.message || 'Failed to archive department')
      }
      
      await fetchDepartments()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to archive department')
    }
  }

  if (loading) return <div>Loading...</div>
  if (error) return <div>Error: {error}</div>

  return (
    <div className="department-list">
      <div className="header">
        <h1>Departments</h1>
        <Link to="/departments/new" className="btn btn-primary">Create Department</Link>
      </div>
      
      <table className="data-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Code</th>
            <th>Status</th>
            <th>Description</th>
            <th>Created</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {departments.map(dept => (
            <tr key={dept.id}>
              <td>
                <Link to={`/departments/${dept.id}`}>{dept.name}</Link>
              </td>
              <td>{dept.code}</td>
              <td>
                <span className={`status status-${dept.status}`}>
                  {dept.status}
                </span>
              </td>
              <td>{dept.description || '-'}</td>
              <td>{new Date(dept.created_at).toLocaleDateString()}</td>
              <td>
                <Link to={`/departments/${dept.id}/edit`} className="btn btn-sm">Edit</Link>
                {dept.status === 'active' && (
                  <button 
                    onClick={() => handleArchive(dept.id)}
                    className="btn btn-sm btn-danger"
                  >
                    Archive
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