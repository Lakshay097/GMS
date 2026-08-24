# External Services Inventory

## Phase 1.5 Verification - Added Dependencies

### Cloudinary (Media & Evidence Storage)
- **Purpose**: Observation evidence file storage per ADR-07
- **Access Pattern**: 
  - Upload: Backend uses Python SDK with credentials from environment
  - Download: Backend generates signed URLs with 1-hour expiry (A7 security fix)
- **Security Model**:
  - Upload: Authenticated via `get_current_user` dependency
  - Storage: `type="authenticated"` for all uploads (A7 security fix)
  - Download: Signed URLs with expiry, generated via `/evidence/signed-url/{observation_id}/{public_id}` endpoint
  - Tenant scoping: Applied at signed URL generation level (new endpoint)
  - URL generation: `use_filename=True`, `unique_filename=True` to prevent predictable IDs
- **Environment Variables Required**:
  - `CLOUDINARY_CLOUD_NAME`
  - `CLOUDINARY_API_KEY`
  - `CLOUDINARY_API_SECRET`
  - `CLOUDINARY_UPLOAD_PRESET`
- **A7 Security Fixes Applied**:
  - Changed upload to `type="authenticated"` (requires signed URLs)
  - Added `/evidence/signed-url/{observation_id}/{public_id}` endpoint with tenant scoping
  - Added `use_filename=True` and `unique_filename=True` to prevent ID guessing
  - Signed URLs expire after 1 hour
- **Risk**: Mitigated - evidence is no longer publicly accessible via URL guessing
- **Rotation Requirements**: Per env-and-secrets.md, rotate `CLOUDINARY_API_SECRET` alongside other secrets

### Neon Auth (Authentication Provider)
- **Purpose**: Primary authentication and session management
- **Access Pattern**: JWT tokens issued by Neon Auth, validated by backend
- **Security Model**: Backend validates Neon Auth tokens using `NEON_AUTH_COOKIE_SECRET`
- **Environment Variables Required**:
  - `NEON_AUTH_BASE_URL`
  - `NEON_AUTH_COOKIE_SECRET`
- **Current Flow**: Neon Auth token → backend validation → session cookie (httpOnly)

### SQS (Task Queue - Phase 1 Default)
- **Purpose**: Async job queue for scheduled tasks
- **Access Pattern**: Backend boto3 SDK with AWS credentials
- **Note**: Currently attributed solely to SQS, not evidence storage

## Note on Original Audit Assumptions
The original audit assumed S3/Boto3 for evidence storage. Verification revealed Cloudinary is actually used. This represents an undocumented external dependency that should be included in future security reviews.