# Environment & Secrets — School Operations & Governance Platform

Purpose: pin the concrete choices Architecture §18 deliberately left open
("recommendation, not binding"), so Prompt 1 doesn't have Devin implicitly
choose a message queue or cache provider on your behalf. Fill in the actual
values before running Prompt 1; this file should never be committed to the
repo with real secret values — commit the *names/structure*, keep values in
your secrets manager / CI environment config.

---

## 1. Environments

Three required (Architecture §17, rules.md): **Dev**, **Staging**,
**Production**. Neon's copy-on-write branching (Architecture §18) makes
per-PR preview databases cheap — recommend one ephemeral Neon branch per
open PR in addition to the three named environments.

| Environment | Purpose | Notes |
|---|---|---|
| Dev | Local/shared development | Scale-to-zero Neon branch acceptable |
| Staging | Pre-prod, runs the Prompt 13 e2e workflow tests | Should mirror Production config, smaller scale |
| Production | Live | MFA, encryption, monitoring all mandatory here (R-56/R-57) |
| PR previews | Per-PR ephemeral | Neon branch-per-PR; tear down on merge/close |

## 2. Database — Neon (serverless PostgreSQL)

```
DATABASE_URL=                     # Neon connection string, per environment
NEON_PROJECT_ID=
NEON_BRANCH_ID=                   # differs per environment/PR-preview
NEON_API_KEY=                     # for branch creation in CI (PR previews)
```

Row-level tenant isolation (school_id/department_id) is enforced in schema,
not via separate databases per school (R-03/ADR-02) — one project, branched
by environment, not by tenant.

## 3. Auth — Neon Auth (Better Auth-backed)

**Correction:** Neon Auth is Better Auth-backed, not Stack Auth-backed —
update the section heading anywhere this file was already referenced in a
Devin prompt. The underlying provider changed on Neon's side since this
file's original draft.

```
NEON_AUTH_BASE_URL=
NEON_AUTH_COOKIE_SECRET=
MFA_REQUIRED_ROLES=Admin,SuperAdmin        # R-56
SESSION_TIMEOUT_MINUTES=                    # Configuration Engine value, PRS §54 — set initial default here, then move to config-engine table on first boot
```

**Frontend-specific client variable — separate from the three keys above:**
```
VITE_NEON_AUTH_URL=          # e.g. https://ep-<branch>.neonauth.c-4.<region>.aws.neon.tech/<db>/auth
```
This is a single branch-specific connection URL used by
`createAuthClient()` on the client side (`@neondatabase/neon-js/auth`) — it
is **not** a substitute for `NEON_AUTH_PROJECT_ID`/`PUBLISHABLE_KEY`/
`SECRET_KEY` above, which the server side still needs. Because it's
branch-specific (each Neon branch — Dev/Staging/Production/PR-preview —
has its own Auth endpoint per §1's environment table), this value changes
per environment the same way `DATABASE_URL` does; pull the current value
from the project's **Auth** page in the Neon console for the branch you're
targeting, not from Credentials (that page issues Object Storage/AI
Gateway credentials and does not carry Auth keys).

**Vite vs. Next.js client — do not mix these:** Architecture.md's Neon
Auth references assume a Next.js-style server+client split
(`@neondatabase/auth/next`, `createNeonAuth()` for server handlers). If the
frontend is Vite/React-Router instead (as scaffolded per the React+Vite
quickstart), the client uses `@neondatabase/neon-js/auth` +
`@neondatabase/neon-js/auth/react` (`NeonAuthUIProvider`, `AuthView`,
`AccountView`) and reads `VITE_NEON_AUTH_URL` directly — there is no
Next.js server-side auth handler in that setup. Confirm which frontend
framework Phase 1 is actually targeting before Prompt 3 (middleware) so
Devin doesn't scaffold the Next.js server-auth pattern against a Vite app,
or vice versa.

SSO/OAuth connector config (AQ5, Phase 2 prep) — leave blank until a
protocol is confirmed, but reserve the keys so the extension point exists:
```
SSO_PROVIDER=            # unset in Phase 1
SSO_CLIENT_ID=
SSO_CLIENT_SECRET=
```

## 4a. School Timezone (required by the Compliance Scheduler, v1.5)

```
DEFAULT_SCHOOL_TIMEZONE=          # IANA tz name, e.g. Asia/Kolkata — School record override, this is only the platform default
```
The Compliance Scheduler (PRS §23.16, BR-24) computes KPI due dates and cycle
boundaries using each School's configured timezone, never server-local time
or UTC — this default seeds new Schools; the authoritative value lives on
the School record itself, not this env file, once the platform is running.

## 4. Media / Document Storage — Cloudinary

```
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
CLOUDINARY_UPLOAD_PRESET=        # for Observation/Checklist evidence
FILE_UPLOAD_MAX_SIZE_MB=          # Configuration Engine value, PRS §54 — set an initial default here
EVIDENCE_RETENTION_PERIOD_DAYS=   # Configuration Engine value, PRS §47/BR-27 — after this elapses evidence becomes deletion-eligible; deletion itself is never automatic (see §11 below)
```

## 5. Async Job Queue (AQ3 — pin your choice here)

Architecture §18 leaves this open pending AQ3 (ordering guarantees for
escalation timers). **Fill in your actual choice before Prompt 1**, don't
let it default implicitly:

```
QUEUE_PROVIDER=            # e.g. sqs | kafka | upstash-qstash | <chosen provider>
QUEUE_CONNECTION_STRING=
```
Recommendation from `assumptions-log.md`: if escalation-timer ordering
matters (it likely does — SLA breach detection depends on in-order
processing), lean toward a Kafka-class provider; confirm with engineering
before Production cutover.

**Phase 1 dev/staging default: Upstash (Kafka or QStash), not SQS.** SQS's
free tier requires an AWS account (and a card on file) even for Dev — no
extra value for a Phase 1 build that's already avoiding AWS-specific SDKs
per AQ1. Upstash gives a Kafka-class ordering guarantee with a no-card
free-tier signup, and its HTTP-based client fits the "abstract queue
interface" requirement (Prompt 1) just as cleanly. Swap to SQS/MSK/etc.
before Production only if engineering sign-off on AQ3 lands on an
AWS-native choice.

## 6. Cache / Session — Redis-class store

```
REDIS_URL=
```
Backs Configuration Engine reads (hot-path config lookups), externalized
session state, and dashboard aggregate caching (Architecture §14/§18).

## 6a. Compliance/Duplicate/Grace-Period Config Defaults (v1.5, Configuration Engine seed values)

```
DUPLICATE_DETECTION_WINDOW_MINUTES=     # BR-25 — default appropriate to KPI Frequency; per-School/Department override via Configuration Engine after boot
GRACE_PERIOD_HOURS=                     # BR-26 — default appropriate to KPI Frequency
SCHEDULER_OUTAGE_GRACE_EXTENSION=       # BR-26/FR-269 — how a backfilled record's Grace Period is extended for scheduler downtime; formula/fixed-offset, confirm with engineering before Prompt 6/9
```
These are seed values only — same pattern as `SESSION_TIMEOUT_MINUTES` and
`FILE_UPLOAD_MAX_SIZE_MB` above: set an initial default here, then the
Configuration Engine table (School override → Department override → Global
default) is authoritative once the platform boots.

## 7. Search Index — OpenSearch/Elasticsearch-class

```
SEARCH_INDEX_URL=
SEARCH_INDEX_API_KEY=
SEARCH_INDEXING_LAG_TARGET_SECONDS=60      # R-60/PRS §51 — do not raise this without stakeholder sign-off
```

**Phase 1 dev/staging default: Meilisearch, not a managed
OpenSearch/Elasticsearch cluster.** Neither OpenSearch nor Elasticsearch
has a meaningful always-free managed tier at this scale; Meilisearch is
MIT-licensed and free to self-host (no feature gating, including hybrid
search) via a single Docker container on the same host/PaaS as the app —
point `SEARCH_INDEX_URL` at that instance. This is a config swap only:
Architecture §18 doesn't mandate OpenSearch specifically, and nothing in
Dashboards/Reports/Search (PRS §30-31, §33) depends on an
OpenSearch-specific query DSL. Revisit before Production only if search
volume/complexity outgrows Meilisearch's feature set.

## 8. Notification Channel Providers

```
EMAIL_PROVIDER_API_KEY=
EMAIL_FROM=                      # Sender email address for Resend (default: onboarding@resend.dev)
SMS_PROVIDER_API_KEY=            # Q4 blocking — cost approval pending, see assumptions-log.md; gate sends behind a feature flag until approved
WHATSAPP_PROVIDER_API_KEY=       # same as above
```

**Phase 1 dev/staging default for email: Resend or Brevo, not SendGrid.**
SendGrid's permanent free plan was retired in 2025 — new accounts now get
only a 60-day trial before paid plans start. Resend (3,000 transactional
emails/month, permanently free) or Brevo (300/day, permanently free) both
cover Phase 1 In-App + Email dispatch (Q4/D2) at zero cost with a
comparable REST API — swap the key/provider here without touching
`/platform/notification-service`'s dispatch logic, since that module
should already be provider-agnostic behind its own interface. SMS/WhatsApp
have no meaningful free tier anywhere; leave those keys blank until Q4/D2
cost approval lands, per the existing note above.

## 9. Feature Flags

```
FEATURE_FLAG_PROVIDER=            # in-house table (Configuration Engine) or third-party — Architecture doesn't mandate either
```
Recommend using the Configuration Engine's own tables (already built in
Prompt 2/4) rather than adding a third-party flag service — one less
external dependency, and flags are already modeled as configuration items.

## 10. Observability

```
LOG_LEVEL=
APM_PROVIDER=
ERROR_TRACKING_DSN=
```
Every 500 error must be logged to the Audit Log per API-Spec §3 — this is
in addition to, not instead of, general APM/error tracking.

## 11. Secrets Handling Rules

- Never commit real values for any variable above — this file documents
  *names and purpose*, actual values live in your CI/CD secrets store or a
  vault, scoped per environment.
- Rotate `NEON_AUTH_COOKIE_SECRET`, `CLOUDINARY_API_SECRET`, and all
  notification-provider keys on a schedule; document that schedule
  wherever your team tracks operational runbooks (not in this repo).
- Production secrets should not be accessible from Dev/Staging CI jobs —
  scope CI secret access per environment, not globally.

## 12. Phase 1 Free-Tier Summary (Dev/Staging cost baseline)

Every provider below can be signed up for at $0 for Dev/Staging-scale
usage — none require a paid plan to start Prompt 1. This is a cost
baseline, not a Production sizing guide; re-check each once real traffic
numbers exist (ties to Q8/AQ2 volume targets).

| Variable block | Phase 1 provider | Free tier | Signup |
|---|---|---|---|
| §2/§3 `DATABASE_URL`, `NEON_*`, `NEON_AUTH_*`, `VITE_NEON_AUTH_URL` | Neon (DB + bundled Auth) | 0.5GB storage, 100 compute-hrs/mo, scale-to-zero, Auth up to 60K MAU | neon.tech, no card — `VITE_NEON_AUTH_URL` from the project's Auth page, per-branch |
| §4 `CLOUDINARY_*` | Cloudinary | 25 credits/mo (1 credit = 1GB storage/bandwidth or 1K transforms), 3 users | cloudinary.com, no card |
| §5 `QUEUE_PROVIDER` | Upstash (Kafka or QStash) | Free tier, no AWS account required | upstash.com, no card |
| §6 `REDIS_URL` | Upstash Redis | 256MB, 500K commands/mo | upstash.com, no card |
| §7 `SEARCH_INDEX_URL` | Meilisearch (self-hosted) | Free forever, MIT license, no feature gating | Docker image, no signup |
| §8 `EMAIL_PROVIDER_API_KEY` | Resend or Brevo | 3,000/mo (Resend) or 300/day (Brevo), permanent | resend.com or brevo.com, no card |
| §8 SMS/WhatsApp | — | No meaningful free tier; stays behind Q4/D2 flag | n/a until cost approved |
| §10 `ERROR_TRACKING_DSN` | Sentry | Developer plan, free forever, capped event volume | sentry.io, no card |
| §10 `APM_PROVIDER` | Grafana Cloud (optional) | 10K metric series, 50GB logs, 50GB traces | grafana.com, no card |

Update this table's provider column if a `BLOCKING`/`ASSUMED` item in
`assumptions-log.md` resolves toward a different vendor (e.g., AQ3
resolving toward SQS for production) — the free-tier choice above is a
Phase 1 dev-cost optimization, not a substitute for that sign-off.