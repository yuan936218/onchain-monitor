"""Pre-built queries used by dashboard components."""

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

    inflow = session.query(func.sum(StablecoinTransfer.value_usd)).filter(
        and_(
            StablecoinTransfer.block_timestamp >= since,
            StablecoinTransfer.to_label.isnot(None),
        )
    ).scalar() or 0

    outflow = session.query(func.sum(StablecoinTransfer.value_usd)).filter(
        and_(
            StablecoinTransfer.block_timestamp >= since,
            StablecoinTransfer.from_label.isnot(None),
        )
    ).scalar() or 0

    large_tx_count = session.query(StablecoinTransfer).filter(
        and_(
            StablecoinTransfer.block_timestamp >= since,
            StablecoinTransfer.value_usd >= 1_000_000,
        )
    ).count()

    mint_count = session.query(MintBurnEvent).filter(
        and_(
            MintBurnEvent.block_timestamp >= since,
            MintBurnEvent.event_type == "mint",
        )
    ).count()

    return {
        "inflow": inflow,
        "outflow": outflow,
        "net_flow": outflow - inflow,  # positive = outflow (accumulation), negative = inflow (sell pressure)
        "large_tx_count": large_tx_count,
        "mint_count": mint_count,
    }


def get_large_transfers(hours=24, min_value_usd=1_000_000, token_filter=None):
    session = get_session()
    since = datetime.utcnow() - timedelta(hours=hours)

    q = session.query(StablecoinTransfer).filter(
        and_(
            StablecoinTransfer.block_timestamp >= since,
            StablecoinTransfer.value_usd >= min_value_usd,
        )
    )

    if token_filter and token_filter != "ALL":
        q = q.filter(StablecoinTransfer.token_symbol == token_filter)

    return q.order_by(StablecoinTransfer.value_usd.desc()).limit(100).all()


def get_exchange_flow_timeseries(hours=24):
    """Return hourly exchange inflow/outflow for the last N hours."""
    session = get_session()
    since = datetime.utcnow() - timedelta(hours=hours)

    transfers = session.query(StablecoinTransfer).filter(
        StablecoinTransfer.block_timestamp >= since
    ).all()

    # Group by hour
    hourly = {}
    for t in transfers:
        hour_key = t.block_timestamp.replace(minute=0, second=0, microsecond=0)
        if hour_key not in hourly:
            hourly[hour_key] = {"inflow": 0, "outflow": 0}
        if t.to_label:  # money going INTO an exchange wallet
            hourly[hour_key]["inflow"] += t.value_usd or 0
        if t.from_label:  # money going OUT of an exchange wallet
            hourly[hour_key]["outflow"] += t.value_usd or 0

    return sorted(
        [{"hour": k, **v} for k, v in hourly.items()],
        key=lambda x: x["hour"]
    )


def get_whale_movements(hours=24):
    session = get_session()
    since = datetime.utcnow() - timedelta(hours=hours)
    return session.query(WhaleMovement).filter(
        WhaleMovement.block_timestamp >= since
    ).order_by(WhaleMovement.value_usd.desc()).all()


def get_recent_mint_burns(hours=24):
    session = get_session()
    since = datetime.utcnow() - timedelta(hours=hours)
    return session.query(MintBurnEvent).filter(
        MintBurnEvent.block_timestamp >= since
    ).order_by(MintBurnEvent.block_timestamp.desc()).all()


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
