"""UTC datetime helpers — prefer over deprecated datetime.utcnow()."""
from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """
    Current UTC time as a naive datetime.

    Model columns use DateTime without timezone=True; store naive UTC
    consistently. Avoids datetime.utcnow() which is removed in future Python.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
