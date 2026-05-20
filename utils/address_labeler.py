"""Resolve blockchain addresses to human-readable labels."""

from database.connection import get_session
from database.models import MonitoredAddress

# In-memory cache for label lookups (cleared on each script rerun via Streamlit's execution model)
_label_cache: dict[str, str | None] = {}


def resolve_label(address: str) -> str | None:
    """Look up an address in monitored_addresses. Returns the label or None."""
    addr = address.lower()
    if addr in _label_cache:
        return _label_cache[addr]

    session = get_session()
    result = session.query(MonitoredAddress).filter(
        MonitoredAddress.address == addr,
        MonitoredAddress.is_active == True,
    ).first()
    label = result.label if result else None
    _label_cache[addr] = label
    return label


def get_category(address: str) -> str | None:
    """Look up an address in monitored_addresses. Returns the category or None."""
    addr = address.lower()
    session = get_session()
    result = session.query(MonitoredAddress).filter(
        MonitoredAddress.address == addr,
        MonitoredAddress.is_active == True,
    ).first()
    return result.category if result else None
