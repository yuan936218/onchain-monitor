"""Pre-built queries used by dashboard components."""

import re
from datetime import datetime, timedelta
from sqlalchemy import func, and_
from database.models import (
    StablecoinTransfer, WhaleMovement, MintBurnEvent, Alert,
    DailyAggregate, MonitoredAddress, PollState,
)
from database.connection import get_session


def get_recent_alerts(limit=50, unacknowledged_only=False):
    session = get_session()
    q = session.query(Alert).order_by(Alert.created_at.desc())
    if unacknowledged_only:
        q = q.filter(Alert.is_acknowledged == False)
    return q.limit(limit).all()


def get_unacknowledged_alert_count():
    session = get_session()
    return session.query(Alert).filter(Alert.is_acknowledged == False).count()


def acknowledge_alert(alert_id):
    session = get_session()
    alert = session.query(Alert).get(alert_id)
    if alert:
        alert.is_acknowledged = True
        session.commit()


def get_24h_aggregates():
    """Return inflow/outflow totals for last 24 hours."""
    session = get_session()
    since = datetime.utcnow() - timedelta(hours=24)

    # Get exchange addresses for matching (more reliable than label checks)
    exchange_addrs = [a[0] for a in session.query(MonitoredAddress.address).filter(
        MonitoredAddress.category == "exchange",
        MonitoredAddress.is_active == True,
    ).all()]

    inflow = 0
    outflow = 0
    large_tx_count = 0
    mint_count = 0

    if exchange_addrs:
        inflow = session.query(func.sum(StablecoinTransfer.value_usd)).filter(
            StablecoinTransfer.detected_at >= since,
            StablecoinTransfer.to_address.in_(exchange_addrs),
        ).scalar() or 0

        outflow = session.query(func.sum(StablecoinTransfer.value_usd)).filter(
            StablecoinTransfer.detected_at >= since,
            StablecoinTransfer.from_address.in_(exchange_addrs),
        ).scalar() or 0

    large_tx_count = session.query(StablecoinTransfer).filter(
        and_(
            StablecoinTransfer.detected_at >= since,
            StablecoinTransfer.value_usd >= 1_000_000,
        )
    ).count()

    mint_count = session.query(MintBurnEvent).filter(
        and_(
            MintBurnEvent.detected_at >= since,
            MintBurnEvent.event_type == "mint",
        )
    ).count()

    return {
        "inflow": float(inflow),
        "outflow": float(outflow),
        "net_flow": float(outflow) - float(inflow),
        "large_tx_count": large_tx_count,
        "mint_count": mint_count,
    }


def get_large_transfers(hours=24, min_value_usd=1_000_000, token_filter=None):
    session = get_session()
    since = datetime.utcnow() - timedelta(hours=hours)

    q = session.query(StablecoinTransfer).filter(
        and_(
            StablecoinTransfer.detected_at >= since,
            StablecoinTransfer.value_usd >= min_value_usd,
        )
    )

    if token_filter and token_filter != "ALL":
        q = q.filter(StablecoinTransfer.token_symbol == token_filter)

    return q.order_by(StablecoinTransfer.value_usd.desc()).limit(100).all()



def get_exchange_flow_timeseries_by_exchange(hours=24):
    """Return hourly inflow/outflow grouped by exchange name.

    Returns dict: exchange_name -> list[{hour, inflow, outflow, net_flow}]
    """
    session = get_session()
    since = datetime.utcnow() - timedelta(hours=hours)

    addresses = session.query(MonitoredAddress.address, MonitoredAddress.label).filter(
        MonitoredAddress.category == "exchange",
        MonitoredAddress.is_active == True,
    ).all()

    if not addresses:
        return {}

    address_to_exchange = {}
    for addr, label in addresses:
        exchange_name = re.sub(r'\s+\d+$', '', label).strip()
        if not exchange_name:
            continue
        address_to_exchange[addr] = exchange_name

    exchange_set = set(address_to_exchange.keys())

    transfers = session.query(StablecoinTransfer).filter(
        StablecoinTransfer.detected_at >= since
    ).all()

    hourly = {}
    for t in transfers:
        hour_key = t.detected_at.replace(minute=0, second=0, microsecond=0)
        if hour_key not in hourly:
            hourly[hour_key] = {}

        if t.to_address in exchange_set:
            name = address_to_exchange[t.to_address]
            hourly[hour_key].setdefault(name, {"inflow": 0, "outflow": 0})
            hourly[hour_key][name]["inflow"] += t.value_usd or 0

        if t.from_address in exchange_set:
            name = address_to_exchange[t.from_address]
            hourly[hour_key].setdefault(name, {"inflow": 0, "outflow": 0})
            hourly[hour_key][name]["outflow"] += t.value_usd or 0

    result = {}
    for hour_key, exchanges in sorted(hourly.items()):
        for name, flows in exchanges.items():
            if name not in result:
                result[name] = []
            result[name].append({
                "hour": hour_key,
                "inflow": flows["inflow"],
                "outflow": flows["outflow"],
                "net_flow": flows["outflow"] - flows["inflow"],
            })

    return result


def get_whale_movements(hours=24):
    session = get_session()
    since = datetime.utcnow() - timedelta(hours=hours)
    return session.query(WhaleMovement).filter(
        WhaleMovement.detected_at >= since
    ).order_by(WhaleMovement.value_usd.desc()).all()


def get_recent_mint_burns(hours=24):
    session = get_session()
    since = datetime.utcnow() - timedelta(hours=hours)
    return session.query(MintBurnEvent).filter(
        MintBurnEvent.detected_at >= since
    ).order_by(MintBurnEvent.detected_at.desc()).all()


def get_active_monitored_addresses(category=None):
    session = get_session()
    q = session.query(MonitoredAddress).filter(MonitoredAddress.is_active == True)
    if category:
        q = q.filter(MonitoredAddress.category == category)
    return q.all()


def get_poll_state(source):
    session = get_session()
    return session.query(PollState).filter(PollState.source == source).first()


def update_poll_state(source, last_block, last_timestamp):
    session = get_session()
    state = session.query(PollState).filter(PollState.source == source).first()
    if state:
        state.last_block = last_block
        state.last_timestamp = last_timestamp
        state.updated_at = datetime.utcnow()
    else:
        state = PollState(
            source=source,
            last_block=last_block,
            last_timestamp=last_timestamp,
        )
        session.add(state)
    session.commit()
