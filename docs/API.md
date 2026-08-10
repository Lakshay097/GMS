# API Documentation

## Overview

The School Operations & Governance Platform exposes a REST API under `/api/v1/`. All endpoints are documented via OpenAPI (auto-generated from source annotations).

## Base URL

- Local development: `http://localhost:8000`
- All endpoints are prefixed with `/api/v1`

## Interactive Documentation

Once the server is running:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## Authentication

Authentication uses Neon Auth (Better Auth-backed). The auth router is included in the API at `/api/v1/auth/*`.

### Headers
- `Authorization: Bearer <token>` - Required for authenticated endpoints
- `Idempotency-Key: <uuid>` - Required for record-creating write endpoints (mandatory on Observation submission)

## Core Endpoints

### Health Check
- `GET /health` - Returns service health status

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "service": "school-operations-platform"
}
```

### Schools (PRS §18)
- `POST /api/v1/schools` - Create school (SuperAdmin only)
- `GET /api/v1/schools` - List schools (SuperAdmin, Viewer with grants)
- `GET /api/v1/schools/{id}` - Get school details
- `PATCH /api/v1/schools/{id}` - Update school (SuperAdmin only)
- `POST /api/v1/schools/{id}/deactivate` - Deactivate school (SuperAdmin only)

### Departments (PRS §19)
- `POST /api/v1/departments` - Create department (SuperAdmin, Admin within own school)
- `GET /api/v1/departments` - List departments (All roles, scoped)
- `GET /api/v1/departments/{id}` - Get department details
- `PATCH /api/v1/departments/{id}` - Update department (SuperAdmin, Admin within own school)
- `POST /api/v1/departments/{id}/archive` - Archive department (SuperAdmin, Admin within own school)

### Users (PRS §20)
- `POST /api/v1/users` - Create user (SuperAdmin, Admin within own school)
- `GET /api/v1/users` - List users (SuperAdmin, Admin within own school)
- `GET /api/v1/users/{id}` - Get user details
- `PATCH /api/v1/users/{id}` - Update user (SuperAdmin, Admin within own school, self)
- `POST /api/v1/users/{id}/archive` - Archive user (SuperAdmin, Admin within own school)
- `POST /api/v1/users/{id}/roles` - Grant role (SuperAdmin, Admin within own school)
- `DELETE /api/v1/users/{id}/roles/{role_code}` - Revoke role (SuperAdmin, Admin within own school)
- `POST /api/v1/users/{id}/school-grants` - Grant school access (SuperAdmin only)

### Configuration (PRS §54)
- `GET /api/v1/configuration/global` - Get global configuration (All roles)
- `PATCH /api/v1/configuration/global` - Update global configuration (SuperAdmin only)
- `GET /api/v1/configuration/schools/{id}` - Get school configuration
- `PATCH /api/v1/configuration/schools/{id}` - Update school configuration (SuperAdmin, Admin within own school)
- `POST /api/v1/configuration/schools/{id}/reset` - Reset school configuration to global defaults

### KRA/KPI Library (PRS §22-23)
- `POST /api/v1/kras` - Create KRA (SuperAdmin only)
- `GET /api/v1/kras` - List KRAs
- `PATCH /api/v1/kras/{kra_id}` - Update KRA (SuperAdmin only)
- `POST /api/v1/kpis` - Create KPI (SuperAdmin only)
- `GET /api/v1/kpis` - List KPIs (optionally filtered by `kra_id`)
- `GET /api/v1/kpis/{kpi_id}` - Get KPI details
- `GET /api/v1/kpis/{kpi_id}/versions` - List KPI versions
- `GET /api/v1/kpis/{kpi_id}/versions/{version}` - Get specific KPI version
- `PATCH /api/v1/kpis/{kpi_id}` - Update KPI (SuperAdmin only)
- `POST /api/v1/kpis/{kpi_id}/deprecate` - Deprecate KPI (SuperAdmin only)
- `POST /api/v1/kpis/import` - Import KPIs from seed file (SuperAdmin only)
- `POST /api/v1/departments/{department_id}/kpi-assignments` - Assign KPI to department
- `POST /api/v1/observations` - Submit observation

## Response Envelope

List endpoints return a standard pagination envelope:

```
json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total_count": 100,
    "has_next": true
  }
}
```

## Error Response Shape

All errors follow the shared error contract (API-Spec §3):

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Target Value must be numeric.",
    "field": "target_value"
  }
}
```

### HTTP Status Codes
| Code | Meaning |
|------|---------|
| 400 | Validation error |
| 401 | Authentication error |
| 403 | Permission/scope error |
| 404 | Not found or not visible (indistinguishable) |
| 409 | Conflict/immutability violation |
| 422 | Business-rule violation |
| 500 | Internal error (always logged to Audit Log) |

## List Endpoint Conventions

- `page` / `page_size` (default 50, max 200)
- Mandatory `from`/`to` date bounding on high-volume endpoints (Observations, Audit Log)
- Unbounded queries rejected with 400
- Response envelope: `{ "data": [...], "pagination": {...} }`
