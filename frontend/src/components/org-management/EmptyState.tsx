import { useState } from 'react'
import SchoolForm from './SchoolForm'
import DepartmentForm from './DepartmentForm'
import KraForm from './KraForm'
import KpiForm from './KpiForm'
import KpiEntryQuickLog from './KpiEntryQuickLog'

type Step = 'school' | 'department' | 'kra' | 'kpi' | 'entry'

const STEPS: { key: Step; title: string; description: string; icon: string }[] = [
  { key: 'school', title: 'Create a School', description: 'Start by adding your first school or institution.', icon: '🏫' },
  { key: 'department', title: 'Add a Department', description: 'Create a department within your school.', icon: '🏢' },
  { key: 'kra', title: 'Define a KRA', description: 'Set up a Key Result Area to group your KPIs.', icon: '🎯' },
  { key: 'kpi', title: 'Create a KPI', description: 'Define a measurable indicator within your KRA.', icon: '📊' },
  { key: 'entry', title: 'Log a Check', description: 'Record your first measurement against a KPI.', icon: '✅' },
]

export default function EmptyState() {
  const [currentStep, setCurrentStep] = useState<Step>('school')
  const [completedSteps, setCompletedSteps] = useState<Set<Step>>(new Set())

  const stepIndex = STEPS.findIndex(s => s.key === currentStep)

  const handleCreated = () => {
    setCompletedSteps(prev => new Set([...prev, currentStep]))
    // Move to next step
    const nextIndex = stepIndex + 1
    if (nextIndex < STEPS.length) {
      setCurrentStep(STEPS[nextIndex].key)
    }
  }

  const renderForm = () => {
    switch (currentStep) {
      case 'school':
        return <SchoolForm onCreated={handleCreated} />
      case 'department':
        return <DepartmentForm onCreated={handleCreated} />
      case 'kra':
        return <KraForm onCreated={handleCreated} />
      case 'kpi':
        return <KpiForm onCreated={handleCreated} />
      case 'entry':
        return <KpiEntryQuickLog onCreated={handleCreated} />
    }
  }

  return (
    <div className="empty-state-container">
      <div className="empty-state-header">
        <h2>Welcome to SchoolOP</h2>
        <p>Set up your organization step by step. Each step builds on the previous one.</p>
      </div>

      {/* Step indicators */}
      <div className="step-indicators">
        {STEPS.map((step) => (
          <div
            key={step.key}
            className={`step-indicator ${step.key === currentStep ? 'active' : ''} ${completedSteps.has(step.key) ? 'completed' : ''}`}
            onClick={() => setCurrentStep(step.key)}
          >
            <span className="step-icon">{completedSteps.has(step.key) ? '✓' : step.icon}</span>
            <span className="step-label">{step.title}</span>
          </div>
        ))}
      </div>

      {/* Current step form */}
      <div className="step-content">
        <h3>{STEPS[stepIndex].title}</h3>
        <p className="step-description">{STEPS[stepIndex].description}</p>
        {renderForm()}
      </div>
    </div>
  )
}
