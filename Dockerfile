# Multi-stage Dockerfile for School Operations & Governance Platform

# ── Stage 1: Build frontend ───────────────────────────────────────────────────
FROM node:22-slim AS frontend-builder

# Vite embeds these at build time via import.meta.env.VITE_*
ARG VITE_CLERK_PUBLISHABLE_KEY
ARG VITE_NEON_AUTH_URL
ARG VITE_SENTRY_FRONTEND_DSN
ARG VITE_DEBUG=false
ENV VITE_CLERK_PUBLISHABLE_KEY=${VITE_CLERK_PUBLISHABLE_KEY}
ENV VITE_NEON_AUTH_URL=${VITE_NEON_AUTH_URL}
ENV VITE_SENTRY_FRONTEND_DSN=${VITE_SENTRY_FRONTEND_DSN}
ENV VITE_DEBUG=${VITE_DEBUG}

WORKDIR /app/frontend
COPY frontend/ ./
RUN rm -rf node_modules && npm install --include=dev
RUN npm run build

# ── Stage 2: Build Python dependencies ────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 3: Production ───────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code (excluding frontend)
COPY api/ ./api/
COPY modules/ ./modules/
COPY platform_services/ ./platform_services/
COPY shared/ ./shared/
COPY migrations/ ./migrations/
COPY alembic.ini ./
COPY requirements.txt ./
COPY .env.example ./

# Copy built frontend from frontend-builder
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

ENV PORT=8000
EXPOSE ${PORT}

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Use shell form so $PORT is expanded at runtime (Cloud Run sets PORT)
CMD uvicorn api.main:app --host 0.0.0.0 --port ${PORT}
