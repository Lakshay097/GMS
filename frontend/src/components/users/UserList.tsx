import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

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
  created_at: string
  archived_at?: string
}

interface UserListResponse {
  data: User[]
  pagination: {
    page: number
    page_size: number
    total_count: number
    has_next: boolean
  }
}

export default function UserList() {
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)

  useEffect(() => {
    fetchUsers()
  }, [page])

  const fetchUsers = async () => {
    try {
      setLoading(true)
      const token = localStorage.getItem('auth_token')
      const response = await fetch(`/api/v1/users?page=${page}&page_size=50`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })
      
      if (!response.ok) {
        throw new Error('Failed to fetch users')
      }
      
      const data: UserListResponse = await response.json()
      setUsers(data.data)
      setTotal(data.pagination.total_count)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const handleArchive = async (userId: string) => {
    if (!confirm('Are you sure you want to archive this user? This will disable their login immediately.')) {
      return
    }

    try {
      const token = localStorage.getItem('auth_token')
      const response = await fetch(`/api/v1/users/${userId}/archive`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error?.message || 'Failed to archive user')
      }
      
      await fetchUsers()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to archive user')
    }
  }

  if (loading) return <div>Loading...</div>
  if (error) return <div>Error: {error}</div>

  return (
    <div className="user-list">
      <div className="header">
        <h1>Users</h1>
        <Link to="/users/new" className="btn btn-primary">Create User</Link>
      </div>
      
      <table className="data-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Roles</th>
            <th>Status</th>
            <th>School</th>
            <th>Department</th>
            <th>Created</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.map(user => (
            <tr key={user.id}>
              <td>
                <Link to={`/users/${user.id}`}>{user.full_name}</Link>
              </td>
              <td>{user.email}</td>
              <td>{user.roles.join(', ')}</td>
              <td>
                <span className={`status status-${user.status}`}>
                  {user.status}
                </span>
              </td>
              <td>{user.school_id || '-'}</td>
              <td>{user.department_id || '-'}</td>
              <td>{new Date(user.created_at).toLocaleDateString()}</td>
              <td>
                <Link to={`/users/${user.id}/edit`} className="btn btn-sm">Edit</Link>
                {user.status === 'active' && (
                  <button 
                    onClick={() => handleArchive(user.id)}
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