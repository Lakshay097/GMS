"""
Webhook endpoint.

The Clerk webhook handler was removed along with Clerk itself. SchoolOps is
fully self-managed for authentication: users are created by Admins via
/api/v1/users or by the `create_admin.py` management command, so there are
no external identity events to consume.

Keep this module so api/main.py imports keep working. Register new webhook
routes here if a future integration needs one (with signature verification).
"""
import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
