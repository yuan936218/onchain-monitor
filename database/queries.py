"""Pre-built queries used by dashboard components."""

import re
from datetime import datetime, timedelta
from sqlalchemy import func, and_
from database.models import (
    StablecoinTransfer, WhaleMovement, MintBurnEvent, Alert,
    DailyAggregate, MonitoredAddress, PollState, ExchangeBalanceSnapshot,
    PriceSnapshot,
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


def get_24h_aggregates(chain=None, token_filter=None):
    """Return inflow/outflow totals for last 24 hours."""
    session = get_session()
    since = datetime.utcnow() - timedelta(hours=24)

    addr_q = session.query(MonitoredAddress.address).filter(
        MonitoredAddress.category == "exchange",
        MonitoredAddress.is_active == True,
    )
    transfer_q = session.query(StablecoinTransfer).filter(
        StablecoinTransfer.detected_at >= since,
    )
    mint_q = session.query(MintBurnEvent).filter(
        MintBurnEvent.detected_at >= since,
        MintBurnEvent.event_type == "mint",
    )

    if chain:
        addr_q = addr_q.filter(MonitoredAddress.chain == chain)
        transfer_q = transfer_q.filter(StablecoinTransfer.chain == chain)
        mint_q = mint_q.filter(MintBurnEvent.chain == chain)
    if token_filter and token_filter != "ALL":
        transfer_q = transfer_q.filter(StablecoinTransfer.token_symbol == token_filter)
        mint_q = mint_q.filter(MintBurnEvent.token_symbol == token_filter)

    exchange_addrs = [a[0] for a in addr_q.all()]

    inflow = 0
    outflow = 0
    large_tx_count = 0
    mint_count = 0

    if exchange_addrs:
        inflow = transfer_q.filter(StablecoinTransfer.to_address.in_(exchange_addrs)).with_entities(
            func.sum(StablecoinTransfer.value_usd)
        ).scalar() or 0

        outflow = transfer_q.filter(StablecoinTransfer.from_address.in_(exchange_addrs)).with_entities(
            func.sum(StablecoinTransfer.value_usd)
        ).scalar() or 0

    large_tx_count = transfer_q.filter(
        StablecoinTransfer.value_usd >= 1_000_000,
    ).count()

    mint_count = mint_q.count()

    return {
        "inflow": float(inflow),
        "outflow": float(outflow),
        "net_flow": float(outflow) - float(inflow),
        "large_tx_count": large_tx_count,
        "mint_count": mint_count,
    }


def get_large_transfers(hours=24, min_value_usd=0, token_filter=None, chain=None):
    session = get_session()
    since = datetime.utcnow() - timedelta(hours=hours)

    q = session.query(StablecoinTransfer).filter(
        StablecoinTransfer.detected_at >= since,
        StablecoinTransfer.value_usd >= min_value_usd,
    )

    if token_filter and token_filter != "ALL":
        q = q.filter(StablecoinTransfer.token_symbol == token_filter)
    if chain:
        q = q.filter(StablecoinTransfer.chain == chain)

    return q.order_by(StablecoinTransfer.value_usd.desc()).limit(100).all()



def get_exchange_flow_timeseries_by_exchange(hours=24, chain=None, token_filter=None):
    """Return hourly inflow/outflow grouped by exchange name.

    Returns dict: exchange_name -> list[{hour, inflow, outflow, net_flow}]
    """
    session = get_session()
    since = datetime.utcnow() - timedelta(hours=hours)

    addr_q = session.query(MonitoredAddress.address, MonitoredAddress.label).filter(
        MonitoredAddress.category == "exchange",
        MonitoredAddress.is_active == True,
    )
    transfer_q = session.query(StablecoinTransfer).filter(
        StablecoinTransfer.detected_at >= since,
    )

    if chain:
        addr_q = addr_q.filter(MonitoredAddress.chain == chain)
        transfer_q = transfer_q.filter(StablecoinTransfer.chain == chain)
    if token_filter and token_filter != "ALL":
        transfer_q = transfer_q.filter(StablecoinTransfer.token_symbol == token_filter)

    addresses = addr_q.all()

    if not addresses:
        return {}

    address_to_exchange = {}
    for addr, label in addresses:
        exchange_name = re.sub(r'\s+\d+$', '', label).strip()
        if not exchange_name:
            continue
        address_to_exchange[addr] = exchange_name

    exchange_set = set(address_to_exchange.keys())

    transfers = transfer_q.all()

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


def get_whale_movements(hours=24, chain=None):
    session = get_session()
    since = datetime.utcnow() - timedelta(hours=hours)
    q = session.query(WhaleMovement).filter(
        WhaleMovement.detected_at >= since
    )
    if chain:
        q = q.filter(WhaleMovement.chain == chain)
    return q.order_by(WhaleMovement.value_usd.desc()).all()


def get_recent_mint_burns(hours=24, chain=None):
    session = get_session()
    since = datetime.utcnow() - timedelta(hours=hours)
    q = session.query(MintBurnEvent).filter(
        MintBurnEvent.detected_at >= since
    )
    if chain:
        q = q.filter(MintBurnEvent.chain == chain)
    return q.order_by(MintBurnEvent.detected_at.desc()).all()


def get_hourly_flow_patterns(days=7, chain=None, token_filter=None):
    """Return average hourly inflow/outflow over the last N days.

    Returns list of 24 dicts [{hour, avg_inflow, avg_outflow, tx_count}]
    """
    session = get_session()
    since = datetime.utcnow() - timedelta(days=days)

    addr_q = session.query(MonitoredAddress.address).filter(
        MonitoredAddress.category == "exchange",
        MonitoredAddress.is_active == True,
    )
    if chain:
        addr_q = addr_q.filter(MonitoredAddress.chain == chain)
    exchange_addrs = [a[0] for a in addr_q.all()]

    if not exchange_addrs:
        return [{"hour": h, "avg_inflow": 0, "avg_outflow": 0, "tx_count": 0} for h in range(24)]

    exchange_set = set(exchange_addrs)

    transfer_q = session.query(StablecoinTransfer).filter(
        StablecoinTransfer.detected_at >= since,
    )
    if chain:
        transfer_q = transfer_q.filter(StablecoinTransfer.chain == chain)
    if token_filter and token_filter != "ALL":
        transfer_q = transfer_q.filter(StablecoinTransfer.token_symbol == token_filter)

    transfers = transfer_q.all()

    # Count distinct days with data
    day_set = set()
    hourly = {h: {"inflow": 0, "outflow": 0, "count": 0} for h in range(24)}

    for t in transfers:
        hour = t.detected_at.hour
        day_set.add(t.detected_at.date())
        if t.to_address in exchange_set:
            hourly[hour]["inflow"] += t.value_usd or 0
            hourly[hour]["count"] += 1
        if t.from_address in exchange_set:
            hourly[hour]["outflow"] += t.value_usd or 0
            hourly[hour]["count"] += 1

    day_count = len(day_set) or 1

    return [
        {
            "hour": h,
            "avg_inflow": hourly[h]["inflow"] / day_count,
            "avg_outflow": hourly[h]["outflow"] / day_count,
            "tx_count": hourly[h]["count"],
        }
        for h in range(24)
    ]


def get_active_monitored_addresses(category=None, chain=None):
    session = get_session()
    q = session.query(MonitoredAddress).filter(MonitoredAddress.is_active == True)
    if category:
        q = q.filter(MonitoredAddress.category == category)
    if chain:
        q = q.filter(MonitoredAddress.chain == chain)
    return q.all()


def get_poll_state(source):
    session = get_session()
    return session.query(PollState).filter(PollState.source == source).first()


def get_exchange_balance_timeseries(hours=24, chain=None, token_filter=None):
    """Return exchange balance snapshots for charting.

    Returns dict: exchange_name -> list[{snapshot_at, token_symbol, balance_usd}]
    """
    session = get_session()
    since = datetime.utcnow() - timedelta(hours=hours)

    q = session.query(ExchangeBalanceSnapshot).filter(
        ExchangeBalanceSnapshot.snapshot_at >= since,
    )
    if chain:
        q = q.filter(ExchangeBalanceSnapshot.chain == chain)
    if token_filter and token_filter != "ALL":
        q = q.filter(ExchangeBalanceSnapshot.token_symbol == token_filter)

    snapshots = q.order_by(
        ExchangeBalanceSnapshot.exchange_name,
        ExchangeBalanceSnapshot.snapshot_at.asc(),
    ).all()

    # Group by exchange, aggregate all tokens per snapshot time
    result = {}
    for s in snapshots:
        name = s.exchange_name
        if name not in result:
            result[name] = []
        # Merge same-timestamp entries by adding balance_usd
        existing = [r for r in result[name] if r["snapshot_at"] == s.snapshot_at]
        if existing:
            existing[0]["balance_usd"] = (existing[0]["balance_usd"] or 0) + (s.balance_usd or 0)
        else:
            result[name].append({
                "snapshot_at": s.snapshot_at,
                "balance_usd": s.balance_usd or 0,
            })

    return result


def get_price_history(hours: int = 24, token_id: str = "ETH"):
    """Return price snapshots for charting.

    Returns list of [{snapshot_at, price_usd}]
    """
    session = get_session()
    since = datetime.utcnow() - timedelta(hours=hours)

    rows = session.query(PriceSnapshot).filter(
        PriceSnapshot.token_id == token_id,
        PriceSnapshot.snapshot_at >= since,
    ).order_by(PriceSnapshot.snapshot_at.asc()).all()

    return [{"snapshot_at": r.snapshot_at, "price_usd": r.price_usd} for r in rows]


def get_market_intel_data(hours: int = 6, chain=None):
    """Aggregate recent data for the market intelligence brief.

    Returns a dict with summary metrics for natural language generation.
    """
    session = get_session()
    since = datetime.utcnow() - timedelta(hours=hours)

    # Exchange addresses
    addr_q = session.query(MonitoredAddress.address, MonitoredAddress.label).filter(
        MonitoredAddress.category == "exchange",
        MonitoredAddress.is_active == True,
    )
    if chain:
        addr_q = addr_q.filter(MonitoredAddress.chain == chain)
    exchange_addrs = addr_q.all()
    exchange_set = {a[0] for a in exchange_addrs}

    # Transfers in window
    tx_q = session.query(StablecoinTransfer).filter(
        StablecoinTransfer.detected_at >= since,
    )
    if chain:
        tx_q = tx_q.filter(StablecoinTransfer.chain == chain)

    transfers = tx_q.all()

    total_inflow = sum(t.value_usd or 0 for t in transfers if t.to_address in exchange_set)
    total_outflow = sum(t.value_usd or 0 for t in transfers if t.from_address in exchange_set)
    large_count = sum(1 for t in transfers if (t.value_usd or 0) >= 10_000_000)

    # Per-exchange flow
    exchange_flows = {}
    for t in transfers:
        if t.to_address in exchange_set:
            name = next((lbl for addr, lbl in exchange_addrs if addr == t.to_address), None)
            if name:
                name = name.rstrip(" 0123456789").strip()
                d = exchange_flows.setdefault(name, {"inflow": 0, "outflow": 0})
                d["inflow"] += t.value_usd or 0
        if t.from_address in exchange_set:
            name = next((lbl for addr, lbl in exchange_addrs if addr == t.from_address), None)
            if name:
                name = name.rstrip(" 0123456789").strip()
                d = exchange_flows.setdefault(name, {"inflow": 0, "outflow": 0})
                d["outflow"] += t.value_usd or 0

    # Whale movements
    whale_q = session.query(WhaleMovement).filter(
        WhaleMovement.detected_at >= since,
    )
    if chain:
        whale_q = whale_q.filter(WhaleMovement.chain == chain)
    whale_moves = whale_q.order_by(WhaleMovement.value_usd.desc()).limit(5).all()

    # Mint/burn
    mint_q = session.query(MintBurnEvent).filter(
        MintBurnEvent.detected_at >= since,
    )
    if chain:
        mint_q = mint_q.filter(MintBurnEvent.chain == chain)
    mint_events = mint_q.all()
    total_mint = sum(e.value_usd or 0 for e in mint_events if e.event_type == "mint")
    total_burn = sum(e.value_usd or 0 for e in mint_events if e.event_type == "burn")

    # Latest balance totals
    from sqlalchemy import and_
    balance_q = session.query(ExchangeBalanceSnapshot).filter(
        ExchangeBalanceSnapshot.snapshot_at >= since,
    )
    if chain:
        balance_q = balance_q.filter(ExchangeBalanceSnapshot.chain == chain)
    balances = balance_q.all()

    exchange_balance_latest = {}
    for b in balances:
        name = b.exchange_name.rstrip(" 0123456789").strip()
        key = (name, b.chain)
        if key not in exchange_balance_latest or b.snapshot_at > exchange_balance_latest[key]["snapshot_at"]:
            exchange_balance_latest[key] = {"balance_usd": b.balance_usd or 0, "snapshot_at": b.snapshot_at}

    # Net balance change signals
    balance_signals = []
    for (name, chain_name), info in exchange_balance_latest.items():
        # Find earliest balance in window to compute change
        earliest = min(
            (b for b in balances if b.exchange_name.rstrip(" 0123456789").strip() == name and b.chain == chain_name),
            key=lambda x: x.snapshot_at,
            default=None,
        )
        if earliest and info["balance_usd"] > 0:
            change = info["balance_usd"] - (earliest.balance_usd or 0)
            if abs(change) > 100_000:  # Only report >$100k changes
                balance_signals.append({
                    "exchange": f"{name} ({chain_name})",
                    "change": change,
                    "current": info["balance_usd"],
                })

    balance_signals.sort(key=lambda x: abs(x["change"]), reverse=True)

    return {
        "hours": hours,
        "total_transfers": len(transfers),
        "total_inflow": total_inflow,
        "total_outflow": total_outflow,
        "net_flow": total_outflow - total_inflow,
        "large_count": large_count,
        "exchange_flows": exchange_flows,
        "whale_moves": [
            {
                "asset": w.asset,
                "value_usd": w.value_usd,
                "from_label": w.from_label,
                "to_label": w.to_label,
                "chain": w.chain,
            }
            for w in whale_moves
        ],
        "total_mint": total_mint,
        "total_burn": total_burn,
        "net_mint": total_mint - total_burn,
        "balance_signals": balance_signals[:5],
    }


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
