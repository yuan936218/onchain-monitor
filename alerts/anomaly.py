"""Statistical anomaly detection for exchange flows — Z-score based."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from sqlalchemy import func
from database.connection import get_session
from database.models import StablecoinTransfer, MonitoredAddress, Alert

logger = logging.getLogger(__name__)


def detect_flow_anomaly():
    """Compare current hour's exchange flow against historical hourly baseline.

    Uses Z-score: (current - mean) / std. Flags when |Z| > 2.
    """
    session = get_session()
    now = datetime.utcnow()
    current_hour_start = now.replace(minute=0, second=0, microsecond=0)

    # Get exchange addresses
    exchange_addrs = [
        a[0] for a in session.query(MonitoredAddress.address).filter(
            MonitoredAddress.category == "exchange",
            MonitoredAddress.is_active == True,
        ).all()
    ]
    if not exchange_addrs:
        return 0

    exchange_set = set(exchange_addrs)

    # Current hour's inflow/outflow
    current_inflow = session.query(func.sum(StablecoinTransfer.value_usd)).filter(
        StablecoinTransfer.detected_at >= current_hour_start,
        StablecoinTransfer.to_address.in_(exchange_set),
    ).scalar() or 0

    current_outflow = session.query(func.sum(StablecoinTransfer.value_usd)).filter(
        StablecoinTransfer.detected_at >= current_hour_start,
        StablecoinTransfer.from_address.in_(exchange_set),
    ).scalar() or 0

    # Historical baseline: same UTC hour over past 14 days
    historical_inflows = []
    historical_outflows = []
    for days_back in range(1, 15):
        day_start = current_hour_start - timedelta(days=days_back)
        day_end = day_start + timedelta(hours=1)

        h_in = session.query(func.sum(StablecoinTransfer.value_usd)).filter(
            StablecoinTransfer.detected_at >= day_start,
            StablecoinTransfer.detected_at < day_end,
            StablecoinTransfer.to_address.in_(exchange_set),
        ).scalar() or 0

        h_out = session.query(func.sum(StablecoinTransfer.value_usd)).filter(
            StablecoinTransfer.detected_at >= day_start,
            StablecoinTransfer.detected_at < day_end,
            StablecoinTransfer.from_address.in_(exchange_set),
        ).scalar() or 0

        historical_inflows.append(h_in)
        historical_outflows.append(h_out)

    # Calculate mean and std (exclude zeros for better baseline)
    non_zero_in = [v for v in historical_inflows if v > 0]
    non_zero_out = [v for v in historical_outflows if v > 0]

    alerts_created = 0

    for label, current_val, historical_vals in [
        ("inflow", current_inflow, non_zero_in),
        ("outflow", current_outflow, non_zero_out),
    ]:
        if not historical_vals or current_val <= 0:
            continue

        mean = sum(historical_vals) / len(historical_vals)
        variance = sum((v - mean) ** 2 for v in historical_vals) / len(historical_vals)
        std = variance ** 0.5

        if std < 1_000_000:
            continue  # Too little historical data for meaningful detection

        z_score = (current_val - mean) / std

        if z_score > 2.0:
            # Check if we already alerted for this hour
            existing = session.query(Alert).filter(
                Alert.alert_type == "flow_anomaly",
                Alert.created_at >= current_hour_start,
                Alert.title.contains(label),
            ).first()
            if existing:
                continue

            multiplier = current_val / mean if mean > 0 else 0
            alert = Alert(
                alert_type="flow_anomaly",
                severity="warning",
                title=f"异常{label}: 当前小时{label}远超历史均值 (Z={z_score:.1f})",
                description=(
                    f"当前小时交易所{label}为 {current_val:,.0f} USD，"
                    f"历史同期均值为 {mean:,.0f} USD (标准差 {std:,.0f})。"
                    f"当前值为历史均值的 {multiplier:.1f}x 倍，偏离程度 Z-score={z_score:.1f}。"
                    f"这可能预示着异常的市场行为，请密切关注。"
                ),
                value_usd=current_val,
            )
            session.add(alert)
            alerts_created += 1
            logger.info(f"[anomaly] Z={z_score:.1f} {label}: current={current_val:,.0f} mean={mean:,.0f} std={std:,.0f}")

    if alerts_created:
        session.commit()

    return alerts_created
