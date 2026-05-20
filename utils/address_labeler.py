"""Resolve blockchain addresses to human-readable labels."""

from functools import lru_cache
from database.connection import get_session
from database.models import MonitoredAddress


@lru_cache(maxsize=1024)
def resolve_label(address: str) -> str | None:
    """Look up an address in monitored_addresses. Returns the label or None."""
    session = get_session()
    result = session.query(MonitoredAddress).filter(
        MonitoredAddress.address == address.lower(),
        MonitoredAddress.is_active == True,
    ).first()
    return result.label if result else None


def get_category(address: str) -> str | None:
    session = get_session()
    result = session.query(MonitoredAddress).filter(
        MonitoredAddress.address == address.lower(),
        MonitoredAddress.is_active == True,
    ).first()
    return result.category if result else None
