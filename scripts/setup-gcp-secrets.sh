#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# setup-gcp-secrets.sh
# Creates all Secret Manager secrets needed for Cloud Run deployment.
# Reads values from .env file (or prompts for them).
#
# Usage:
#   chmod +x scripts/setup-gcp-secrets.sh
#   ./scripts/setup-gcp-secrets.sh                  # reads from .env
#   ./scripts/setup-gcp-secrets.sh /path/to/.env    # reads from custom path
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - Secret Manager API enabled
#   - A .env file with your secret values
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

PROJECT_ID="school-operations-platform"
ENV_FILE="${1:-.env}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

created=0
updated=0

# ── Helpers ───────────────────────────────────────────────────────────────────

# Read a value from the .env file
env_val() {
  local key="$1"
  local default="${2:-}"
  local val
  val=$(grep -E "^${key}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d'=' -f2- || true)
  if [[ -n "$val" ]]; then
    echo "$val"
  else
    echo "$default"
  fi
}

# Auto-generate a random secret
gen_secret() {
  python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null \
    || openssl rand -base64 32 | tr -d '='
}

# Create or update a Secret Manager secret
put_secret() {
  local name="$1"
  local value="$2"

  if [[ -z "$value" ]]; then
    echo -e "  ${YELLOW}EMPTY${NC}   $name — add later with:"
    echo -e "           echo -n 'VALUE' | gcloud secrets versions add $name --data-file=-"
    return
  fi

  if gcloud secrets describe "$name" --project="$PROJECT_ID" &>/dev/null; then
    echo -n "$value" | gcloud secrets versions add "$name" --project="$PROJECT_ID" --data-file=- 2>/dev/null
    echo -e "  ${GREEN}UPDATED${NC}  $name"
    updated=$((updated + 1))
  else
    echo -n "$value" | gcloud secrets create "$name" \
      --project="$PROJECT_ID" \
      --replication-policy="automatic" \
      --data-file=- 2>/dev/null
    echo -e "  ${GREEN}CREATE${NC}   $name"
    created=$((created + 1))
  fi
}

# ── Verify gcloud ────────────────────────────────────────────────────────────

echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  GCP Secret Manager Setup — School Operations Platform${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

if [[ ! -f "$ENV_FILE" ]]; then
  echo -e "${RED}ERROR: .env file not found at $ENV_FILE${NC}"
  echo "Usage: $0 [path/to/.env]"
  exit 1
fi

ACTIVE_ACCOUNT=$(gcloud auth list --filter="status:ACTIVE" --format="value(account)" 2>/dev/null | head -1)
if [[ -z "$ACTIVE_ACCOUNT" ]]; then
  echo -e "${RED}ERROR: gcloud not authenticated. Run: gcloud auth login${NC}"
  exit 1
fi
echo -e "Account: ${GREEN}$ACTIVE_ACCOUNT${NC}"
echo -e "Project: ${GREEN}$PROJECT_ID${NC}"
echo -e "Env:     ${GREEN}$ENV_FILE${NC}"
echo ""

if ! gcloud projects describe "$PROJECT_ID" &>/dev/null; then
  echo -e "${RED}ERROR: Project $PROJECT_ID not found${NC}"
  exit 1
fi

# ── Auto-generate secrets ────────────────────────────────────────────────────

echo -e "${CYAN}── Auto-generated secrets ──${NC}"
put_secret "PLATFORM_JWT_SECRET" "$(gen_secret)"
put_secret "INTERNAL_SCHEDULER_SECRET" "$(gen_secret)"
echo ""

# ── Database ─────────────────────────────────────────────────────────────────

echo -e "${CYAN}── Database ──${NC}"
put_secret "DATABASE_URL" "$(env_val DATABASE_URL)"
put_secret "DATABASE_READ_REPLICA_URL" "$(env_val DIRECT_URL)"
echo ""

# ── Neon ─────────────────────────────────────────────────────────────────────

echo -e "${CYAN}── Neon ──${NC}"
put_secret "NEON_PROJECT_ID" "$(env_val NEON_PROJECT_ID)"
put_secret "NEON_BRANCH_ID" "$(env_val NEON_BRANCH_ID)"
put_secret "NEON_API_KEY" "$(env_val NEON_API_KEY)"
echo ""

# ── Neon Auth ────────────────────────────────────────────────────────────────

echo -e "${CYAN}── Neon Auth ──${NC}"
put_secret "NEON_AUTH_BASE_URL" "$(env_val NEON_AUTH_BASE_URL)"
put_secret "NEON_AUTH_COOKIE_SECRET" "$(env_val NEON_AUTH_COOKIE_SECRET)"
echo ""

# ── Clerk ────────────────────────────────────────────────────────────────────

echo -e "${CYAN}── Clerk ──${NC}"
put_secret "CLERK_SECRET_KEY" "$(env_val CLERK_SECRET_KEY)"
put_secret "CLERK_JWKS_URL" "$(env_val CLERK_JWKS_URL)"
put_secret "CLERK_WEBHOOK_SECRET" "$(env_val CLERK_WEBHOOK_SECRET)"
put_secret "VITE_CLERK_PUBLISHABLE_KEY" "$(env_val VITE_CLERK_PUBLISHABLE_KEY)"
echo ""

# ── Security ─────────────────────────────────────────────────────────────────

echo -e "${CYAN}── Security ──${NC}"
put_secret "ENCRYPTION_KEY" "$(env_val ENCRYPTION_KEY)"
# Frontend is co-located on the same Cloud Run service, so CORS is not needed
# for same-origin requests. Only set this if external origins need API access.
put_secret "CORS_ORIGINS" ""
echo ""

# ── Redis ────────────────────────────────────────────────────────────────────

echo -e "${CYAN}── Redis ──${NC}"
REDIS_URL="$(env_val REDIS_URL | sed 's|redis-cli --tls -u ||')"
put_secret "REDIS_URL" "$REDIS_URL"
put_secret "QUEUE_CONNECTION_STRING" "$REDIS_URL"
echo ""

# ── Cloudinary ───────────────────────────────────────────────────────────────

echo -e "${CYAN}── Cloudinary ──${NC}"
put_secret "CLOUDINARY_CLOUD_NAME" "$(env_val CLOUDINARY_CLOUD_NAME)"
put_secret "CLOUDINARY_API_KEY" "$(env_val CLOUDINARY_API_KEY)"
put_secret "CLOUDINARY_API_SECRET" "$(env_val CLOUDINARY_API_SECRET)"
put_secret "CLOUDINARY_UPLOAD_PRESET" "$(env_val CLOUDINARY_UPLOAD_PRESET)"
echo ""

# ── Search ───────────────────────────────────────────────────────────────────

echo -e "${CYAN}── Search ──${NC}"
put_secret "SEARCH_INDEX_URL" "$(env_val SEARCH_INDEX_URL)"
put_secret "SEARCH_INDEX_API_KEY" "$(env_val SEARCH_INDEX_API_KEY)"
echo ""

# ── Email ────────────────────────────────────────────────────────────────────

echo -e "${CYAN}── Email (Resend) ──${NC}"
put_secret "EMAIL_PROVIDER_API_KEY" "$(env_val EMAIL_PROVIDER_API_KEY)"
put_secret "EMAIL_FROM" "onboarding@resend.dev"
echo ""

# ── SMS / WhatsApp (Phase 2) ────────────────────────────────────────────────

echo -e "${CYAN}── SMS / WhatsApp (Phase 2) ──${NC}"
put_secret "SMS_PROVIDER_API_KEY" "$(env_val SMS_PROVIDER_API_KEY)"
put_secret "WHATSAPP_PROVIDER_API_KEY" "$(env_val WHATSAPP_PROVIDER_API_KEY)"
echo ""

# ── Sentry ───────────────────────────────────────────────────────────────────

echo -e "${CYAN}── Sentry ──${NC}"
put_secret "SENTRY_BACKEND_DSN" "$(env_val SENTRY_BACKEND_DSN)"
put_secret "SENTRY_FRONTEND_DSN" "$(env_val SENTRY_FRONTEND_DSN)"
put_secret "VITE_SENTRY_FRONTEND_DSN" "$(env_val SENTRY_FRONTEND_DSN)"
echo ""

# ── Cloud Scheduler ──────────────────────────────────────────────────────────

echo -e "${CYAN}── Cloud Scheduler ──${NC}"
put_secret "CLOUD_SCHEDULER_IP_RANGES" "34.118.0.0/20,34.149.0.0/20,130.211.0.0/22,35.199.224.0/19"
echo ""

# ── Vite build args ──────────────────────────────────────────────────────────

echo -e "${CYAN}── Vite build args ──${NC}"
put_secret "VITE_NEON_AUTH_URL" "$(env_val NEON_AUTH_BASE_URL)"
echo ""

# ── Summary ──────────────────────────────────────────────────────────────────

echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  SUMMARY${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "  ${GREEN}Created:${NC}  $created new secrets"
echo -e "  ${GREEN}Updated:${NC}  $updated secrets (new version added)"
echo ""
echo -e "  ${YELLOW}Secrets still needing values (not in .env):${NC}"
echo -e "    • VITE_CLERK_PUBLISHABLE_KEY — Clerk Dashboard → API Keys"
echo -e "    • SEARCH_INDEX_API_KEY — Meilisearch (empty for local dev)"
echo -e "    • SMS_PROVIDER_API_KEY — Phase 2"
echo -e "    • WHATSAPP_PROVIDER_API_KEY — Phase 2"
echo ""
echo -e "  Then trigger a build:"
echo -e "  ${GREEN}gcloud builds submit --config=cloudbuild.yaml .${NC}"
echo ""
