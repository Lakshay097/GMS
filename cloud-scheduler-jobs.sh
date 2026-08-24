#!/bin/bash
# Cloud Scheduler job configuration commands
# These are gcloud commands to set up the scheduled jobs
# Replace PROJECT_ID and REGION with your actual values

# Set your project ID
PROJECT_ID="your-project-id"
REGION="us-central1"
SERVICE_NAME="school-operations-api"
INTERNAL_SCHEDULER_SECRET="your-internal-scheduler-secret"

# Service account for Cloud Scheduler (create if needed)
# gcloud iam service-accounts create scheduler-sa --display-name="Cloud Scheduler Service Account"
# gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:scheduler-sa@$PROJECT_ID.iam.gserviceaccount.com" --role="roles/cloudrun.invoker"

# Get the Cloud Run service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)')

echo "Setting up Cloud Scheduler jobs for: $SERVICE_URL"

# Compliance Scheduler - Daily at midnight UTC
gcloud scheduler jobs create compliance-scheduler-daily \
  --schedule="0 0 * * *" \
  --time-zone="UTC" \
  --http-target-uri="$SERVICE_URL/internal/scheduler/compliance-check" \
  --http-target-method="POST" \
  --http-target-oidc-service-account-email="scheduler-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --http-target-oidc-audience="$SERVICE_URL" \
  --headers="X-Scheduler-Secret=$INTERNAL_SCHEDULER_SECRET" \
  --description="Daily compliance scheduler run" \
  --retry-count=3 \
  --max-backoff=3600s

# Escalation Scheduler - Every 15 minutes
gcloud scheduler jobs create escalation-scheduler-15min \
  --schedule="*/15 * * * *" \
  --time-zone="UTC" \
  --http-target-uri="$SERVICE_URL/internal/scheduler/escalation-check" \
  --http-target-method="POST" \
  --http-target-oidc-service-account-email="scheduler-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --http-target-oidc-audience="$SERVICE_URL" \
  --headers="X-Scheduler-Secret=$INTERNAL_SCHEDULER_SECRET" \
  --description="Escalation check every 15 minutes" \
  --retry-count=2 \
  --max-backoff=1800s

# Grace Period Sweep - Hourly
gcloud scheduler jobs create grace-period-sweep-hourly \
  --schedule="0 * * * *" \
  --time-zone="UTC" \
  --http-target-uri="$SERVICE_URL/internal/scheduler/grace-period-sweep" \
  --http-target-method="POST" \
  --http-target-oidc-service-account-email="scheduler-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --http-target-oidc-audience="$SERVICE_URL" \
  --headers="X-Scheduler-Secret=$INTERNAL_SCHEDULER_SECRET" \
  --description="Hourly grace period sweep" \
  --retry-count=2 \
  --max-backoff=1800s

# Scorecard Generation - This is typically triggered by review completion, not scheduled
# This is a fallback/example for manual testing
gcloud scheduler jobs create scorecard-generation-test \
  --schedule="0 2 * * *" \
  --time-zone="UTC" \
  --http-target-uri="$SERVICE_URL/internal/scheduler/scorecard-generation" \
  --http-target-method="POST" \
  --http-target-body='{"review_id": "PLACEHOLDER_REVIEW_ID"}' \
  --http-target-oidc-service-account-email="scheduler-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --http-target-oidc-audience="$SERVICE_URL" \
  --headers="X-Scheduler-Secret=$INTERNAL_SCHEDULER_SECRET" \
  --description="Test scorecard generation (manual)" \
  --retry-count=2 \
  --max-backoff=1800s

echo "Cloud Scheduler jobs created successfully!"
echo "Note: The scorecard-generation-test job requires a valid review_id to be useful."