"""Alert rule definitions — Chinese alert messages."""

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


def _get_threshold(key: str, default: float) -> float:
    """Get threshold from Streamlit session state (sidebar) or config default."""
    try:
        import streamlit as st
        value = st.session_state.get(key)
        if value is not None:
            return float(value)
    except Exception:
        pass
    return float(default)


def rule_large_exchange_inflow():
    """Alert: large single-tx stablecoin inflow into an exchange (sell pressure signal)."""
    threshold = _get_threshold("threshold_inflow", THRESHOLD_EXCHANGE_INFLOW)
    session = get_session()
    recent = session.query(StablecoinTransfer).filter(
        and_(
            StablecoinTransfer.value_usd >= threshold,
            StablecoinTransfer.to_label.isnot(None),
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

        alert = Alert(
            alert_type="large_exchange_inflow",
            severity="critical",
            title=f"大额资金流入 {tx.to_label}",
            description=(
                f"{tx.value:,.2f} {tx.token_symbol} 流入 {tx.to_label} "
                f"(约 ${tx.value_usd:,.0f} USD)。可能预示抛售压力，注意风险。"
            ),
            related_tx_hash=tx.tx_hash,
            value_usd=tx.value_usd,
        )
        session.add(alert)
        alerts_created += 1

    session.commit()
    return alerts_created


def rule_large_transfer():
    """Alert: any large transfer above threshold."""
    threshold = _get_threshold("threshold_large", THRESHOLD_LARGE_TRANSFER)
    session = get_session()
    recent = session.query(StablecoinTransfer).filter(
        and_(
            StablecoinTransfer.value_usd >= threshold,
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
        direction = "转入交易所" if tx.to_label else ("转出交易所" if tx.from_label else "链上转账")

        alert = Alert(
            alert_type="large_transfer",
            severity="warning",
            title=f"大额转账: {tx.value:,.2f} {tx.token_symbol}",
            description=(
                f"{tx.value:,.2f} {tx.token_symbol} (约 ${tx.value_usd:,.0f} USD) "
                f"从 {from_info} 至 {to_info} ({direction})。"
            ),
            related_tx_hash=tx.tx_hash,
            value_usd=tx.value_usd,
        )
        session.add(alert)
        alerts_created += 1

    session.commit()
    return alerts_created


def rule_exchange_flow_surge():
    """Alert: total exchange inflow exceeds surge threshold within 10 minutes."""
    threshold = _get_threshold("threshold_inflow", THRESHOLD_EXCHANGE_FLOW_SURGE)
    session = get_session()
    since = datetime.utcnow() - timedelta(minutes=10)

    total_inflow = session.query(func.sum(StablecoinTransfer.value_usd)).filter(
        and_(
            StablecoinTransfer.detected_at >= since,
            StablecoinTransfer.to_label.isnot(None),
        )
    ).scalar() or 0

    if total_inflow >= threshold:
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
            title=f"交易所资金涌入: 10分钟内流入 ${total_inflow:,.0f}",
            description=(
                f"最近10分钟检测到异常大量稳定币流入交易所 "
                f"(总计约 ${total_inflow:,.0f} USD)。这通常预示即将出现抛售压力。"
            ),
            value_usd=total_inflow,
        )
        session.add(alert)
        session.commit()
        return 1

    return 0
