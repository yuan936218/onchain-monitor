"""Alert rule definitions."""

from datetime import datetime, timedelta
from database.connection import get_session
from database.models import StablecoinTransfer, Alert
from config.settings import (
    THRESHOLD_LARGE_TRANSFER,
    THRESHOLD_EXCHANGE_INFLOW,
    THRESHOLD_EXCHANGE_FLOW_SURGE,
    THRESHOLD_WHALE_MOVE,
)
from sqlalchemy import func, and_


def rule_large_exchange_inflow():
    """Alert when a single stablecoin transfer into an exchange exceeds threshold."""
    session = get_session()
    # Find recent large inflows that haven't been alerted yet
    recent = session.query(StablecoinTransfer).filter(
        and_(
            StablecoinTransfer.value_usd >= THRESHOLD_EXCHANGE_INFLOW,
            StablecoinTransfer.to_label.isnot(None),
            StablecoinTransfer.detected_at >= datetime.utcnow() - timedelta(minutes=10),
        )
    ).all()

    alerts_created = 0
    for tx in recent:
        # Deduplicate: check if alert exists for this tx
        existing = session.query(Alert).filter(
            Alert.related_tx_hash == tx.tx_hash
        ).first()
        if existing:
            continue

        alert = Alert(
            alert_type="large_exchange_inflow",
            severity="critical",
            title=f"Large inflow to {tx.to_label}",
            description=(
                f"{tx.value:,.2f} {tx.token_symbol} flowed INTO {tx.to_label} "
                f"(≈${tx.value_usd:,.0f} USD). Potential sell pressure incoming."
            ),
            related_tx_hash=tx.tx_hash,
            value_usd=tx.value_usd,
        )
        session.add(alert)
        alerts_created += 1

    session.commit()
    return alerts_created


def rule_large_transfer():
    """Alert on any stablecoin transfer above the large transfer threshold."""
    session = get_session()
    recent = session.query(StablecoinTransfer).filter(
        and_(
            StablecoinTransfer.value_usd >= THRESHOLD_LARGE_TRANSFER,
            StablecoinTransfer.detected_at >= datetime.utcnow() - timedelta(minutes=10),
        )
    ).all()

    alerts_created = 0
    for tx in recent:
        existing = session.query(Alert).filter(
            Alert.related_tx_hash == tx.tx_hash
        ).first()
        if existing:
            continue

        from_info = tx.from_label or tx.from_address[:10]
        to_info = tx.to_label or tx.to_address[:10]
        direction = "to exchange" if tx.to_label else ("from exchange" if tx.from_label else "between addresses")

        alert = Alert(
            alert_type="large_transfer",
            severity="warning",
            title=f"Large transfer: {tx.value:,.2f} {tx.token_symbol}",
            description=(
                f"{tx.value:,.2f} {tx.token_symbol} (≈${tx.value_usd:,.0f} USD) "
                f"transferred from {from_info} to {to_info} ({direction})."
            ),
            related_tx_hash=tx.tx_hash,
            value_usd=tx.value_usd,
        )
        session.add(alert)
        alerts_created += 1

    session.commit()
    return alerts_created


def rule_exchange_flow_surge():
    """Alert when total exchange inflow in last 10 minutes exceeds threshold."""
    session = get_session()
    since = datetime.utcnow() - timedelta(minutes=10)

    total_inflow = session.query(func.sum(StablecoinTransfer.value_usd)).filter(
        and_(
            StablecoinTransfer.block_timestamp >= since,
            StablecoinTransfer.to_label.isnot(None),
        )
    ).scalar() or 0

    if total_inflow >= THRESHOLD_EXCHANGE_FLOW_SURGE:
        # Deduplicate: check if similar alert was created recently
        existing = session.query(Alert).filter(
            and_(
                Alert.alert_type == "exchange_flow_surge",
                Alert.created_at >= datetime.utcnow() - timedelta(minutes=15),
            )
        ).first()
        if existing:
            return 0

        alert = Alert(
            alert_type="exchange_flow_surge",
            severity="critical",
            title=f"Exchange inflow surge: ${total_inflow:,.0f} in 10 minutes",
            description=(
                f"Massive stablecoin inflow to exchanges detected in the last 10 minutes "
                f"(total ≈${total_inflow:,.0f} USD). This often precedes sell pressure."
            ),
            value_usd=total_inflow,
        )
        session.add(alert)
        session.commit()
        return 1

    return 0
