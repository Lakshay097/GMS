# Cloud Run Deployment Guide

This document provides comprehensive information for deploying the School Operations & Governance Platform to Google Cloud Run with Cloud Scheduler integration.

## Environment Variables

### Database Configuration
- `DATABASE_URL`: PostgreSQL connection string (Neon serverless PostgreSQL)
- `DATABASE_READ_REPLICA_URL`: Read replica connection string for reports/dashboards (optional in dev)
- `NEON_PROJECT_ID`: Neon project ID
- `NEON_BRANCH_ID`: Neon branch ID
- `NEON_API_KEY`: Neon API key

### Authentication
- `NEON_AUTH_BASE_URL`: Neon Auth base URL
- `NEON_AUTH_COOKIE_SECRET`: Neon Auth cookie secret
- `MFA_REQUIRED_ROLES`: Comma-separated list of roles requiring MFA (default: Admin,SuperAdmin)
- `SESSION_TIMEOUT_MINUTES`: Session timeout in minutes (default: 30)

### SSO/OAuth (Phase 2 - leave blank in Phase 1)
- `SSO_PROVIDER`: SSO provider name
- `SSO_CLIENT_ID`: SSO client ID
- `SSO_CLIENT_SECRET`: SSO client secret

### Scheduler Configuration
- `DEFAULT_SCHOOL_TIMEZONE`: Default timezone for schools (default: Asia/Kolkata)

### Media Storage
- `CLOUDINARY_CLOUD_NAME`: Cloudinary cloud name
- `CLOUDINARY_API_KEY`: Cloudinary API key
- `CLOUDINARY_API_SECRET`: Cloudinary API secret
- `CLOUDINARY_UPLOAD_PRESET`: Cloudinary upload preset
- `FILE_UPLOAD_MAX_SIZE_MB`: Maximum file upload size in MB (default: 10)
- `EVIDENCE_RETENTION_PERIOD_DAYS`: Evidence retention period in days (default: 90)

### Queue Configuration
- `QUEUE_PROVIDER`: Queue provider (options: memory, sqs, kafka, upstash-qstash, redis)
- `QUEUE_CONNECTION_STRING`: Queue connection string (for Redis: redis://host:port)

### Redis Configuration
- `REDIS_URL`: Redis connection string (for cache/session storage)

### Compliance Configuration
- `DUPLICATE_DETECTION_WINDOW_MINUTES`: Duplicate detection window in minutes (default: 60)
- `GRACE_PERIOD_HOURS`: Default grace period in hours (default: 24)
- `SCHEDULER_OUTAGE_GRACE_EXTENSION`: Scheduler outage grace extension (default: 2)

### Search Configuration
- `SEARCH_INDEX_URL`: Meilisearch URL (default: http://localhost:7700)
- `SEARCH_INDEX_API_KEY`: Meilisearch API key
- `SEARCH_INDEXING_LAG_TARGET_SECONDS`: Target search indexing lag in seconds (default: 60)

### Notification Providers
- `EMAIL_PROVIDER_API_KEY`: Email provider API key (Resend)
- `EMAIL_FROM`: Sender email address for Resend (default: onboarding@resend.dev)
- `SMS_PROVIDER_API_KEY`: SMS provider API key
- `WHATSAPP_PROVIDER_API_KEY`: WhatsApp provider API key

### Feature Flags
- `FEATURE_FLAG_PROVIDER`: Feature flag provider (default: configuration-engine)

### Security & CORS
- `INTERNAL_SCHEDULER_SECRET`: Secret for Cloud Scheduler authentication
- `CORS_ORIGINS`: Comma-separated list of allowed CORS origins (default: *)

### Observability
- `LOG_LEVEL`: Logging level (default: info)
- `APM_PROVIDER`: APM provider (optional)
- `ERROR_TRACKING_DSN`: Error tracking DSN (optional)

## Secret Management

### Using Google Secret Manager

Sensitive values should be stored in Google Secret Manager rather than environment variables:

#### Required Secrets
1. `school-operations-internal-scheduler-secret`: Secret for Cloud Scheduler authentication
2. `database-url`: Database connection string
3. `neon-api-key`: Neon API key
4. `neon-auth-cookie-secret`: Neon Auth cookie secret
5. `cloudinary-api-secret`: Cloudinary API secret
6. `email-provider-api-key`: Email provider API key
7. `sms-provider-api-key`: SMS provider API key
8. `whatsapp-provider-api-key`: WhatsApp provider API key

#### Creating Secrets
```bash
# Create a secret
gcloud secrets create school-operations-internal-scheduler-secret --data-file="secret.txt"

# Add a secret version
echo "your-secret-value" | gcloud secrets versions add school-operations-internal-scheduler-secret --data-file=-

# Grant Cloud Run service account access to secrets
gcloud secrets add-iam-policy-binding school-operations-internal-scheduler-secret \
  --member="serviceAccount:YOUR_SERVICE_ACCOUNT@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

#### Accessing Secrets in Cloud Run
The Cloud Build configuration (`cloudbuild.yaml`) already includes secret configuration:
```yaml
--set-secrets=INTERNAL_SCHEDULER_SECRET=school-operations-internal-scheduler-secret:latest
```

## Deployment Steps

### 1. Build and Deploy to Cloud Run
```bash
# Set your project ID
export PROJECT_ID="your-project-id"

# Build and deploy using Cloud Build
gcloud builds submit --config cloudbuild.yaml .
```

### 2. Set Up Cloud Scheduler Jobs
```bash
# Make the script executable
chmod +x cloud-scheduler-jobs.sh

# Edit the script with your project ID and secret
nano cloud-scheduler-jobs.sh

# Run the script to create scheduler jobs
./cloud-scheduler-jobs.sh
```

### 3. Create Service Account for Cloud Scheduler
```bash
# Create service account
gcloud iam service-accounts create scheduler-sa \
  --display-name="Cloud Scheduler Service Account"

# Grant Cloud Run invoker role
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:scheduler-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/cloudrun.invoker"
```

### 4. Set Up Upstash Redis
1. Create an Upstash Redis database
2. Get the Redis connection string (redis://default:password@host:port)
3. Set `QUEUE_CONNECTION_STRING` and `REDIS_URL` environment variables

### 5. Verify Deployment
```bash
# Check Cloud Run service status
gcloud run services describe school-operations-api --region=us-central1

# Test health endpoint
curl https://school-operations-api-PROJECT_ID.run.app/health

# Test internal scheduler endpoint (with secret)
curl -X POST https://school-operations-api-PROJECT_ID.run.app/internal/scheduler/compliance-check \
  -H "X-Scheduler-Secret: your-secret"
```

## Scheduler Idempotency and Locking

### Safe for Concurrent Execution
- **ComplianceScheduler.run()**: Protected by database unique constraint
- **ChecklistScheduler.run_for_school()**: Protected by database unique constraint
- **TaskEscalationScheduler.run_check()**: Checks existing escalations before creating new ones

### Requires Distributed Locking
- **ComplianceScheduler.sweep_grace_periods()**: Updates multiple rows without uniqueness constraints
- **ScorecardScheduler.run_generation()**: Has race condition in version resolution

### Implementing Redis-based Locking
For the jobs requiring locking, implement Redis-based distributed locking:

```python
import asyncio
from shared.task_queue import get_queue_instance

async def with_distributed_lock(lock_key: str, ttl: int = 60):
    """Acquire distributed lock using Redis."""
    queue = get_queue_instance()
    lock_acquired = False
    
    try:
        # Attempt to acquire lock
        lock_acquired = await queue.redis_client.set(
            f"lock:{lock_key}", 
            "locked", 
            nx=True, 
            ex=ttl
        )
        
        if not lock_acquired:
            raise Exception("Could not acquire distributed lock")
        
        # Execute critical section
        yield
        
    finally:
        if lock_acquired:
            # Release lock
            await queue.redis_client.delete(f"lock:{lock_key}")
```

## Monitoring and Observability

### Cloud Run Monitoring
- **Metrics**: CPU, memory, request count, latency, error rates
- **Logs**: Cloud Logging integration
- **Tracing**: Cloud Trace (if APM provider configured)

### Cloud Scheduler Monitoring
- **Job execution logs**: Available in Cloud Logging
- **Success/failure metrics**: Available in Cloud Monitoring
- **Alerting**: Set up alert policies for failed job executions

### Redis Monitoring
- **Connection metrics**: Available in Upstash dashboard
- **Memory usage**: Monitor Redis memory consumption
- **Queue depth**: Monitor queue length for job backlogs

## Troubleshooting

### Common Issues

1. **Scheduler jobs failing with 403**
   - Verify `INTERNAL_SCHEDULER_SECRET` is set correctly
   - Check Cloud Scheduler service account has `roles/cloudrun.invoker`
   - Verify the secret is passed in the `X-Scheduler-Secret` header

2. **Redis connection failures**
   - Verify `QUEUE_CONNECTION_STRING` is correct
   - Check Upstash Redis database is accessible
   - Verify network connectivity between Cloud Run and Upstash

3. **Database connection issues**
   - Verify `DATABASE_URL` is correct
   - Check Neon database is accessible
   - Verify network connectivity

4. **Grace period sweep inconsistencies**
   - Implement distributed locking as mentioned above
   - Consider reducing scheduler frequency if issues persist

## Rollback Procedure

If deployment issues occur:

```bash
# List previous revisions
gcloud run revisions list --service=school-operations-api --region=us-central1

# Rollback to previous revision
gcloud run services update-traffic school-operations-api \
  --region=us-central1 \
  --to-revisions=REVISION_NAME=100
```

## Security Considerations

1. **Secret Management**: Always use Secret Manager for sensitive values
2. **Least Privilege**: Grant only necessary IAM roles to service accounts
3. **Network Security**: Consider using VPC connectors for private network access
4. **HTTPS Enforcement**: Cloud Run automatically enforces HTTPS
5. **Scheduler Authentication**: Use both OIDC tokens and shared secret headers for defense in depth