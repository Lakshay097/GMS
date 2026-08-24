import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../lib/api'
import SearchableSelect from '../common/SearchableSelect'

interface School {
  id: string
  name: string
  code: string
}

interface Department {
  id: string
  name: string
  code: string
}

interface FormData {
  schoolCode: string
  schoolId: string
  schoolName: string
  departmentId: string
  departmentName: string
  fullName: string
  phone: string
}

interface FormErrors {
  schoolCode?: string
  fullName?: string
}

export default function PublicSignup() {
  const navigate = useNavigate()
  const [step, setStep] = useState<'school' | 'department' | 'confirmation'>('school')
  const [formData, setFormData] = useState<FormData>({
    schoolCode: '',
    schoolId: '',
    schoolName: '',
    departmentId: '',
    departmentName: '',
    fullName: '',
    phone: ''
  })
  const [errors, setErrors] = useState<FormErrors>({})
  const [schools, setSchools] = useState<School[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [loading, setLoading] = useState(false)
  const [validatingSchool, setValidatingSchool] = useState(false)
  const [confirmationData, setConfirmationData] = useState<{
    schoolName: string
    departmentName?: string
    autoApproved: boolean
  } | null>(null)

  // Load schools for reference
  useEffect(() => {
    const loadSchools = async () => {
      try {
        const response = await apiFetch('/api/v1/schools?page=1&page_size=200')
        if (response.ok) {
          const data = await response.json()
          setSchools(data.data || [])
        }
      } catch (err) {
        console.error('Failed to load schools:', err)
      }
    }
    loadSchools()
  }, [])

  // Load departments when school is selected
  useEffect(() => {
    if (formData.schoolId) {
      const loadDepartments = async () => {
        try {
          const response = await apiFetch(`/api/v1/departments?school_id=${formData.schoolId}`)
          if (response.ok) {
            const data = await response.json()
            setDepartments(data.data || [])
          }
        } catch (err) {
          console.error('Failed to load departments:', err)
        }
      }
      loadDepartments()
    } else {
      setDepartments([])
    }
  }, [formData.schoolId])

  const validateSchoolCode = async (code: string) => {
    if (!code) {
      setErrors(prev => ({ ...prev, schoolCode: 'School code is required' }))
      return false
    }

    setValidatingSchool(true)
    try {
      const response = await apiFetch(`/api/v1/schools?code=${code}`)
      if (response.ok) {
        const data = await response.json()
        if (data.data && data.data.length > 0) {
          const school = data.data[0]
          setFormData(prev => ({
            ...prev,
            schoolId: school.id,
            schoolName: school.name
          }))
          setErrors(prev => ({ ...prev, schoolCode: undefined }))
          setValidatingSchool(false)
          return true
        } else {
          setErrors(prev => ({ ...prev, schoolCode: 'Invalid school code' }))
          setValidatingSchool(false)
          return false
        }
      } else {
        setErrors(prev => ({ ...prev, schoolCode: 'Invalid school code' }))
        setValidatingSchool(false)
        return false
      }
    } catch (err) {
      console.error('Failed to validate school code:', err)
      setErrors(prev => ({ ...prev, schoolCode: 'Failed to validate school code' }))
      setValidatingSchool(false)
      return false
    }
  }

  const handleSchoolSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const isValid = await validateSchoolCode(formData.schoolCode)
    if (isValid) {
      setStep('department')
    }
  }

  const handleDepartmentSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    const newErrors: FormErrors = {}
    if (!formData.fullName.trim()) {
      newErrors.fullName = 'Full name is required'
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }

    setLoading(true)

    try {
      // Check if department auto-accepts
      let autoApproved = false
      let departmentName = formData.departmentName

      if (formData.departmentId) {
        const deptResponse = await apiFetch(`/api/v1/departments/${formData.departmentId}`)
        if (deptResponse.ok) {
          const deptData = await deptResponse.json()
          autoApproved = deptData.auto_accept_requests || false
        }
      }

      // Update Clerk user metadata with signup data
      // This would be done via Clerk SDK - placeholder for now
      // In production, this would call Clerk's API to update user metadata
      // before redirecting to the confirmation screen

      setConfirmationData({
        schoolName: formData.schoolName,
        departmentName: departmentName || undefined,
        autoApproved
      })
      setStep('confirmation')
    } catch (err) {
      console.error('Failed to submit signup:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleSkipDepartment = () => {
    setFormData(prev => ({ ...prev, departmentId: '', departmentName: '' }))
    handleDepartmentSubmit(new Event('submit') as any)
  }

  if (step === 'confirmation' && confirmationData) {
    return (
      <div className="signup-container">
        <div className="signup-card">
          <div className="signup-header">
            <h1>You're in!</h1>
            <p className="signup-subtitle">
              You have Viewer access to {confirmationData.schoolName}
            </p>
          </div>

          <div className="confirmation-content">
            {confirmationData.departmentName ? (
              <div className="confirmation-item">
                {confirmationData.autoApproved ? (
                  <p className="confirmation-success">
                    You've been added to {confirmationData.departmentName}
                  </p>
                ) : (
                  <p className="confirmation-pending">
                    Your request to join {confirmationData.departmentName} is pending approval
                  </p>
                )}
              </div>
            ) : (
              <div className="confirmation-item">
                <p className="confirmation-info">
                  You can request to join a department later from your dashboard
                </p>
              </div>
            )}

            <button
              onClick={() => navigate('/dashboard')}
              className="btn btn-primary btn-full"
            >
              Go to Dashboard
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="signup-container">
      <div className="signup-card">
        {step === 'school' ? (
          <>
            <div className="signup-header">
              <h1>Sign Up</h1>
              <p className="signup-subtitle">Enter your school code to get started</p>
            </div>

            <form onSubmit={handleSchoolSubmit} className="signup-form">
              <div className="form-group">
                <label htmlFor="schoolCode">School Code</label>
                <input
                  id="schoolCode"
                  type="text"
                  value={formData.schoolCode}
                  onChange={(e) => setFormData(prev => ({ ...prev, schoolCode: e.target.value.toUpperCase() }))}
                  onBlur={() => validateSchoolCode(formData.schoolCode)}
                  placeholder="e.g., ABC123"
                  className="form-input"
                  disabled={validatingSchool}
                />
                {errors.schoolCode && (
                  <span className="form-error">{errors.schoolCode}</span>
                )}
                {validatingSchool && (
                  <span className="form-help">Validating school code...</span>
                )}
              </div>

              <button
                type="submit"
                className="btn btn-primary btn-full"
                disabled={validatingSchool || !formData.schoolCode}
              >
                {validatingSchool ? 'Validating...' : 'Continue'}
              </button>
            </form>
          </>
        ) : (
          <>
            <div className="signup-header">
              <h1>Complete Your Profile</h1>
              <p className="signup-subtitle">
                Joining {formData.schoolName}
              </p>
            </div>

            <form onSubmit={handleDepartmentSubmit} className="signup-form">
              <div className="form-group">
                <label htmlFor="fullName">Full Name</label>
                <input
                  id="fullName"
                  type="text"
                  value={formData.fullName}
                  onChange={(e) => setFormData(prev => ({ ...prev, fullName: e.target.value }))}
                  placeholder="Enter your full name"
                  className="form-input"
                />
                {errors.fullName && (
                  <span className="form-error">{errors.fullName}</span>
                )}
              </div>

              <div className="form-group">
                <label htmlFor="phone">Phone (Optional)</label>
                <input
                  id="phone"
                  type="tel"
                  value={formData.phone}
                  onChange={(e) => setFormData(prev => ({ ...prev, phone: e.target.value }))}
                  placeholder="Enter your phone number"
                  className="form-input"
                />
              </div>

              <div className="form-group">
                <label htmlFor="department">Department (Optional)</label>
                <SearchableSelect
                  id="department"
                  name="department"
                  value={formData.departmentId}
                  onChange={(value) => {
                    const dept = departments.find(d => d.id === value)
                    setFormData(prev => ({
                      ...prev,
                      departmentId: value,
                      departmentName: dept?.name || ''
                    }))
                  }}
                  options={departments.map(dept => ({
                    value: dept.id,
                    label: dept.name,
                    sublabel: dept.code
                  }))}
                  placeholder="Select a department"
                  unsetLabel="No department selected"
                />
              </div>

              <button
                type="submit"
                className="btn btn-primary btn-full"
                disabled={loading}
              >
                {loading ? 'Creating Account...' : 'Complete Sign Up'}
              </button>

              <button
                type="button"
                onClick={handleSkipDepartment}
                className="btn btn-ghost btn-full"
                disabled={loading}
              >
                Skip for now
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  )
}
