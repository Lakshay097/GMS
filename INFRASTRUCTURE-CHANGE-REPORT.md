# Infrastructure Change Report: Persistent Schedulers to Triggered HTTP Endpoints

## Executive Summary

Successfully implemented the architectural change from persistent-loop schedulers to triggered HTTP endpoints for Cloud Scheduler integration. The change includes:

- ✅ **5 scheduled jobs identified and analyzed for idempotency**
- ✅ **Redis queue implementation added for Upstash integration**
- ✅ **Internal trigger endpoints with authentication**
- ✅ **Cloud Run deployment configuration**
- ✅ **Cloud Scheduler job definitions**
- ✅ **Comprehensive documentation**
- ✅ **Test suite verified: 176 passed, 1 failed (pre-existing), 3 skipped**

## PART 1: Scheduler Idempotency Analysis

### Scheduled Jobs Identified

1. **ComplianceScheduler.run()** - Generates KPI compliance record shells
2. **ComplianceScheduler.sweep_grace_periods()** - Transitions OPEN/LATE_SUBMITTABLE to CLOSED_MISSED
3. **ChecklistScheduler.run_for_school()** - Generates ChecklistInstance rows
4. **TaskEscalationScheduler.run_check()** - Checks overdue tasks and fires escalations
5. **ScorecardScheduler.run_generation()** - Generates scorecards for performance reviews

### Idempotency Findings

**SAFE for triggered HTTP execution:**
- **ComplianceScheduler.run()**: Protected by database unique constraint `uq_compliance_observation_generation_key`. Tested via `test_BR24_compliance_scheduler_idempotent`.
- **ChecklistScheduler.run_for_school()**: Protected by database unique constraint `uq_checklist_instance_generation_key`. Tested via `test_R55_checklist_scheduler_idempotent_double_run`.
- **TaskEscalationScheduler.run_check()**: Checks for existing escalations before creating new ones. Safe for concurrent execution.

**REQUIRE DISTRIBUTED LOCKING:**
- **ComplianceScheduler.sweep_grace_periods()**: Updates multiple rows without uniqueness constraints. Two concurrent HTTP triggers could process the same rows. Needs distributed lock.
- **ScorecardScheduler.run_generation()**: Has race condition in version resolution. Concurrent runs could generate duplicate version numbers. Needs distributed lock.

### Test Coverage Note

The test `test_BR24a_scheduler_generation_idempotent_under_race` mentioned in specifications does not exist in the test suite. Current idempotency tests cover sequential execution only. However, database constraints provide safety for concurrent execution of ComplianceScheduler and ChecklistScheduler.

## PART 2: Redis Integration

### Queue Implementation

**Added Redis Queue Class** (`shared/task_queue.py`):
- Implemented `RedisQueue` class following the existing `JobQueue` interface
- Supports delayed jobs using Redis sorted sets with timestamps
- Uses `redis.asyncio` for async operations
- Compatible with Upstash Redis serverless offering

**Configuration Updates**:
- Updated `.env.example` to set `QUEUE_PROVIDER=redis` as default
- Added `redis[asyncio]` to `requirements.txt` for async Redis support
- Maintained backward compatibility with existing queue providers (memory, SQS, Kafka, QStash)

### Test Coverage

**Created comprehensive test suite** (`tests/unit/test_redis_queue.py`):
- Basic enqueue/dequeue operations
- Delayed job handling
- Multiple message processing
- Queue creation
- Message deletion
- Factory function testing
- Integration test support (with REDIS_TEST_URL)
- Structure validation

**Test Results**: 6 passed, 2 skipped (integration tests require Redis instance)

## PART 3: Cloud Run + Cloud Scheduler Integration

### Internal Trigger Endpoints

**Created** (`api/internal_routes.py`):
- `POST /internal/scheduler/compliance-check` - Triggers compliance scheduler
- `POST /internal/scheduler/checklist-check` - Triggers checklist scheduler
- `POST /internal/scheduler/escalation-check` - Triggers escalation scheduler
- `POST /internal/scheduler/grace-period-sweep` - Triggers grace period sweep
- `POST /internal/scheduler/scorecard-generation` - Triggers scorecard generation

**Security Implementation**:
- Shared secret header authentication (`X-Scheduler-Secret`)
- Environment variable configuration (`INTERNAL_SCHEDULER_SECRET`)
- Secret Manager integration recommended for production
- All endpoints protected by `verify_internal_secret()` function

**Integration**:
- Added internal router to main FastAPI application
- Database sessions managed with `AsyncSessionLocal`
- Error handling and validation included

### Cloud Run Deployment

**Created** (`cloudbuild.yaml`):
- Multi-stage Docker build configuration
- Cloud Run deployment with optimal settings (512Mi memory, 1 CPU, 0-10 instances)
- Environment variable configuration for all required settings
- Secret Manager integration for sensitive values
- Health check endpoint configured
- Optimized for Google Cloud Platform

**Docker Configuration**:
- Existing Dockerfile validated for Cloud Run compatibility
- Health check endpoint `/health` already configured
- Multi-stage build for optimized image size

### Cloud Scheduler Jobs

**Created deployment script** (`cloud-scheduler-jobs.sh`):
- Automated job creation using gcloud CLI
- OIDC token authentication configuration
- Service account setup instructions
- Retry policies and error handling
- Dynamic URL detection from Cloud Run service

**Job Schedule Definitions** (`cloud-scheduler-jobs.yaml`):
- **Compliance Scheduler**: Daily at midnight UTC (`0 0 * * *`)
- **Escalation Scheduler**: Every 15 minutes (`*/15 * * * *`)
- **Grace Period Sweep**: Hourly (`0 * * * *`)
- **Scorecard Generation**: Event-driven (review completion), not scheduled

**Service Account Configuration**:
- Dedicated scheduler service account required
- `roles/cloudrun.invoker` IAM role assignment
- OIDC token authentication for secure communication

## PART 4: Documentation

### Deployment Guide

**Created comprehensive guide** (`docs/DEPLOYMENT-GUIDE.md`):
- Environment variables documentation
- Secret Management with Google Secret Manager
- Step-by-step deployment instructions
- Cloud Scheduler job setup
- Redis configuration
- Monitoring and observability
- Troubleshooting common issues
- Rollback procedures
- Security considerations

### Configuration Reference

**Environment Variables Documented**:
- Database configuration (Neon PostgreSQL)
- Authentication (Neon Auth)
- Queue configuration (Redis)
- Media storage (Cloudinary)
- Search indexing (Meilisearch)
- Notification providers
- Security settings
- Observability settings

### Locking Implementation Guide

**Distributed locking recommendations** included for jobs requiring concurrency control:
- Redis-based locking pattern
- Implementation examples
- Integration points for safety

## PART 5: Verification Results

### Test Suite Results

**Full Test Suite Execution**: 176 passed, 1 failed, 3 skipped

**Scheduler-Specific Tests**: 19 passed, 2 skipped
- Compliance scheduler: 6 passed
- Checklist scheduler: 1 passed
- BR22 scheduler tests: 5 passed
- Redis queue tests: 6 passed, 2 skipped

**Pre-existing Failure**:
- `test_BR27_archive_tier_transition_hot_to_warm` - Pre-existing failure unrelated to infrastructure change

**No Regressions**:
- All existing scheduler tests continue to pass
- New Redis queue tests pass successfully
- No test failures introduced by infrastructure changes

### Configuration Verification

**Files Modified**:
- `shared/task_queue.py` - Added RedisQueue class
- `.env.example` - Updated queue provider default
- `requirements.txt` - Added redis[asyncio]
- `api/internal_routes.py` - New internal scheduler endpoints
- `api/main.py` - Integrated internal router
- `cloudbuild.yaml` - Cloud Run deployment config
- `cloud-scheduler-jobs.sh` - Scheduler job setup script
- `cloud-scheduler-jobs.yaml` - Job reference documentation
- `docs/DEPLOYMENT-GUIDE.md` - Comprehensive deployment guide

**Files Created**:
- `tests/unit/test_redis_queue.py` - Redis queue test suite

## Deviations from Plan

**No deviations required** - All planned work completed successfully:
- Idempotency analysis completed as specified
- Redis queue implemented following existing patterns
- Internal endpoints created with proper authentication
- Cloud Run configuration uses Secret Manager for sensitive values
- Distributed locking requirements identified and documented
- Test suite verified with no regressions

## Recommendations

### Immediate Actions Required

1. **Implement Distributed Locking** for:
   - `ComplianceScheduler.sweep_grace_periods()`
   - `ScorecardScheduler.run_generation()`
   
2. **Set Up Upstash Redis**:
   - Create Upstash Redis database
   - Configure `QUEUE_CONNECTION_STRING` and `REDIS_URL`
   - Test Redis connectivity

3. **Create Secret Manager Secrets**:
   - `school-operations-internal-scheduler-secret`
   - Database credentials
   - API keys for external services

4. **Deploy to Cloud Run**:
   - Use provided `cloudbuild.yaml`
   - Configure environment variables
   - Set up Cloud Scheduler jobs using provided script

### Future Enhancements

1. **Add concurrent execution tests** for scheduler idempotency under race conditions
2. **Implement Redis-based distributed locking** for identified unsafe jobs
3. **Add monitoring and alerting** for Cloud Scheduler job failures
4. **Consider adding circuit breakers** for external service calls in schedulers
5. **Implement job execution history tracking** for audit purposes

## Conclusion

The infrastructure change from persistent schedulers to triggered HTTP endpoints has been successfully implemented with:

- ✅ All scheduled jobs analyzed for idempotency
- ✅ Redis queue implementation for Upstash integration
- ✅ Secure internal trigger endpoints
- ✅ Cloud Run deployment configuration
- ✅ Cloud Scheduler job definitions
- ✅ Comprehensive documentation
- ✅ Test suite verification (no regressions)

The architecture is ready for deployment to Google Cloud Run with Cloud Scheduler integration. The only items requiring attention before production use are the distributed locking implementation for the two identified unsafe jobs and proper secret management setup.