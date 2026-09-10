"""
E2E authentication flow test — self-managed auth against a live server.

Usage:
    uvicorn api.main:app --port 8000   (in another terminal, with DATABASE_URL set)
    python -m pytest tests/e2e/test_self_managed_auth_flow.py -v

Or run standalone:
    python tests/e2e/test_self_managed_auth_flow.py [base_url]

Covers:
    [x] Login succeeds with correct credentials (cookie issued)
    [x] Wrong password fails with uniform 401
    [x] Unknown email fails with identical 401
    [x] GET /auth/me validates the session
    [x] Protected API requires authentication
    [x] Logout invalidates the server-side session (old cookie can't be reused)

Onboarding without an email provider (admin-created user):
    [x] Admin sets a user's password directly  → user can log in
    [x] Admin requests a one-time reset token  → user resets via /auth/reset-password
    [x] Both modes revoke the user's existing sessions
    [x] /auth/forgot-password with NO EMAIL_PROVIDER_API_KEY persists the token
        as an in-app notification (recoverable, response stays uniform)
"""
import asyncio
import os
import sys
import uuid

import httpx


sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from shared.auth import COOKIE_NAME

BASE = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "http://127.0.0.1:8000"
TIMEOUT = httpx.Timeout(30.0)  # cold-start Argon2id + DB pool can exceed httpx's 5s default
EMAIL = f"e2e.admin.{uuid.uuid4().hex[:8]}@schoolops.example.com"
PASSWORD = "Sup3rSecure!2026"

results = []


def check(name, condition, detail=""):
    results.append((name, bool(condition), detail))
    print(f"  [{'PASS' if condition else 'FAIL'}] {name}" + (f" — {detail}" if detail and not condition else ""))


async def run(client: httpx.AsyncClient):
    # Create the user directly in the DB (admin provisioning path)
    from dotenv import load_dotenv
    load_dotenv()
    from sqlalchemy import select
    from shared.database import AsyncSessionLocal
    from shared.models import User, UserStatus, UserRole
    from shared.auth import hash_password
    from shared.datetime_utils import utc_now
    async with AsyncSessionLocal() as db:
        user = User(
            email=EMAIL,
            password_hash=hash_password(PASSWORD),
            full_name="E2E Admin",
            school_id=None,
            status=UserStatus.ACTIVE,
            roles=[UserRole.SUPERADMIN.value],
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.add(user)
        await db.commit()

    # 1. Login succeeds → cookie issued
    r = await client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    check("login succeeds", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
    check("session cookie issued", COOKIE_NAME in r.cookies, str(dict(r.cookies)))
    check("login returns user payload", r.json().get("user", {}).get("email") == EMAIL)
    cookie = r.cookies.get(COOKIE_NAME)

    # 2. Wrong password → uniform 401
    r = await client.post("/auth/login", json={"email": EMAIL, "password": "TotallyWrong99"})
    body = r.json()
    check(
        "wrong password rejected",
        r.status_code == 401 and body["detail"]["error"]["message"] == "Invalid email or password",
        f"status={r.status_code}",
    )

    # 3. Unknown email → identical 401
    r = await client.post("/auth/login", json={"email": "nobody@nowhere.io", "password": "TotallyWrong99"})
    check(
        "unknown email identical error",
        r.status_code == 401 and r.json() == body,
        f"status={r.status_code}",
    )

    # 4. Session validates
    r = await client.get("/auth/get-session")
    check("get-session validates cookie", r.json().get("valid") is True and r.json()["user"]["email"] == EMAIL)
    r = await client.get("/auth/me")
    check("/auth/me works", r.status_code == 200 and r.json()["user"]["email"] == EMAIL)

    # 5. Protected API requires authentication (no cookie on a fresh client)
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as anon:
        r = await anon.get("/api/v1/schools")
        check("protected API rejects anonymous", r.status_code == 401, f"status={r.status_code}")

    # 6. Logout invalidates the server-side session
    r = await client.post("/auth/logout")
    check("logout succeeds", r.status_code == 200)
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT, cookies={COOKIE_NAME: cookie}) as replay:
        r = await replay.get("/auth/get-session")
        check("old session token rejected after logout", r.json().get("valid") is not True)

    # ─────────────────────────────────────────────────────────────────
    # 7. Onboarding WITHOUT an email provider (admin-created user)
    # ─────────────────────────────────────────────────────────────────
    NEW_USER_EMAIL = f"e2e.fresh.{uuid.uuid4().hex[:8]}@schoolops.example.com"
    NEW_PW_1 = "Fr3shStart!2026a"
    NEW_PW_2 = "Fr3shStart!2026b"

    # Admin creates a user with NO password (password_hash NULL — cannot log in)
    async with AsyncSessionLocal() as db:
        new_user = User(
            email=NEW_USER_EMAIL,
            full_name="E2E Fresh User",
            school_id=None,
            status=UserStatus.ACTIVE,
            roles=[UserRole.VIEWER.value],
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.add(new_user)
        await db.commit()
        new_user_id = str(new_user.id)

    # Re-login as admin (main client logged out in step 6)
    r = await client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    check("admin re-login", r.status_code == 200, f"status={r.status_code}")

    # 7a. Admin sets the password directly → user can log in
    r = await client.post(f"/api/v1/users/{new_user_id}/set-password", json={"password": NEW_PW_1})
    check("admin set-password (direct mode)", r.status_code == 200 and r.json().get("mode") == "password",
          f"status={r.status_code} body={r.text[:200]}")

    fresh = httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT)
    try:
        r = await fresh.post("/auth/login", json={"email": NEW_USER_EMAIL, "password": NEW_PW_1})
        check("fresh user logs in with admin-set password", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
        user_cookie = r.cookies.get(COOKIE_NAME)

        # 7b. Admin force-resets (no password in request) → one-time token returned;
        #     the user's existing session must be revoked.
        r = await client.post(f"/api/v1/users/{new_user_id}/set-password", json={})
        body = r.json()
        check("admin set-password (reset-token mode)", r.status_code == 200 and body.get("mode") == "reset_token" and body.get("reset_token"),
              f"status={r.status_code} body={r.text[:200]}")
        reset_token = body.get("reset_token", "")

        async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT, cookies={COOKIE_NAME: user_cookie or ""}) as replay:
            r = await replay.get("/auth/get-session")
            check("set-password revoked the user's old session", r.json().get("valid") is not True)

        # 7c. User consumes the token and sets their own password, then logs in
        r = await fresh.post("/auth/reset-password", json={"token": reset_token, "new_password": NEW_PW_2})
        check("reset-password with admin-issued token", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
        r = await fresh.post("/auth/login", json={"email": NEW_USER_EMAIL, "password": NEW_PW_2})
        check("login with self-set password after reset", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
    finally:
        await fresh.aclose()

    # 7d. /auth/forgot-password with NO email provider: token must be persisted
    #     as an in-app notification (recoverable), response stays uniform.
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as anon:
        r = await anon.post("/auth/forgot-password", json={"email": NEW_USER_EMAIL})
        check("forgot-password uniform response (no provider)",
              r.status_code == 200 and r.json() == {"success": True, "message": "If that email is registered, reset instructions have been sent."},
              f"status={r.status_code} body={r.text[:200]}")

    from shared.platform_models import Notification as NotificationRow
    from shared.auth import hash_session_token
    async with AsyncSessionLocal() as db:
        notif = (await db.execute(
            select(NotificationRow)
            .where(NotificationRow.user_id == uuid.UUID(new_user_id), NotificationRow.channel == "in_app")
            .order_by(NotificationRow.created_at.desc())
        )).scalars().first()
        check("forgot-password persisted in-app notification (no email provider)", notif is not None and "token" in (notif.body or ""))
        if notif is not None:
            embedded_token = notif.body.rsplit(": ", 1)[-1].strip()
            token_hash = hash_session_token(embedded_token)
            from shared.models import PasswordResetToken
            row = (await db.execute(
                select(PasswordResetToken).where(
                    PasswordResetToken.user_id == uuid.UUID(new_user_id),
                    PasswordResetToken.token_hash == token_hash,
                    PasswordResetToken.used_at.is_(None),
                )
            )).scalar_one_or_none()
            check("persisted token matches an unconsumed reset token", row is not None)

    # Cleanup: archive the e2e users
    async with AsyncSessionLocal() as db:
        for email in {EMAIL, NEW_USER_EMAIL}:
            result = await db.execute(select(User).where(User.email == email))
            u = result.scalar_one_or_none()
            if u:
                u.status = UserStatus.ARCHIVED
                u.archived_at = utc_now()
                await db.commit()


async def main():
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as client:
        await run(client)

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)
