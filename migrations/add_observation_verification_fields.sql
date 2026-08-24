-- Add verification status and tracking fields to observations table
-- Migration for KPI verification/reject endpoints

ALTER TABLE observations 
ADD COLUMN status VARCHAR(20) DEFAULT 'pending' NOT NULL,
ADD CONSTRAINT check_observation_status CHECK (status IN ('pending', 'verified', 'rejected')),
ADD COLUMN verified_at TIMESTAMP NULL,
ADD COLUMN verified_by UUID REFERENCES users(id) ON DELETE SET NULL,
ADD COLUMN rejected_at TIMESTAMP NULL,
ADD COLUMN rejected_by UUID REFERENCES users(id) ON DELETE SET NULL,
ADD COLUMN rejection_reason TEXT NULL;

-- Add index for efficient status filtering
CREATE INDEX idx_observations_status ON observations(status);