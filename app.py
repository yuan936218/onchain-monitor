"""On-Chain Data Monitoring Dashboard — Main Entry Point."""

import json
import sys
import os
import copy
import time
import logging
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st

# Page config must be the first Streamlit call
st.set_page_config(
    page_title="链上数据监控",
    page_icon="🔍",
    layout="wide",
)

from database.migrations import init_database
from database.connection import get_session
from database.models import MonitoredAddress
from config.settings import ETHERSCAN_API_KEY
from database.queries import get_unacknowledged_alert_count

# Dashboard components
from dashboard.sidebar import render_sidebar
from dashboard.alerts_panel import render_alerts
from dashboard.metrics_row import render_metrics
from dashboard.exchange_flow_chart import render_exchange_flow_chart
from dashboard.transfer_table import render_transfer_table
from dashboard.mint_burn_timeline import render_mint_burn_timeline
from dashboard.whale_movements import render_whale_movements
from dashboard.hourly_heatmap import render_hourly_heatmap
from dashboard.exchange_balance_chart import render_exchange_balance_chart
from dashboard.price_flow_chart import render_price_flow_chart
from dashboard.market_intel import render_market_intel

logging.basicConfig(level=logging.INFO)

# Initialize database (cached across reruns)
@st.cache_resource
def _init_db():
    init_database()
    seed_addresses_inner()
    return True


def seed_addresses_inner():
    """Seed monitored_addresses table from config/addresses.json."""
    from database.connection import ScopedSession
    session = get_session()
    try:
        config_path = os.path.join(os.path.dirname(__file__), "config", "addresses.json")
        with open(config_path, "r") as f:
            data = json.load(f)

        seeded = 0
        for chain, categories in data.items():
            for category, addresses in categories.items():
                for addr in addresses:
                    exists = session.query(MonitoredAddress).filter(
                        MonitoredAddress.address == addr["address"].lower(),
                        MonitoredAddress.chain == chain,
                    ).first()
                    if exists:
                        continue
                    session.add(MonitoredAddress(
                        address=addr["address"].lower(),
                        label=addr["label"],
                        category="exchange" if category == "exchanges" else category,
                        chain=chain,
                        notes=addr.get("notes", ""),
                    ))
                    seeded += 1

        session.commit()
        return seeded
    finally:
        ScopedSession.remove()


_init_db()


def setup_scheduler():
    """Start background collectors WITHOUT blocking page render.

    A one-shot catch-up job fires immediately, then the regular
    interval collector takes over. This avoids the white screen on first
    load — the dashboard renders instantly with "waiting for first collection"
    status, then auto-refreshes when data arrives.
    """
    from apscheduler.schedulers.background import BackgroundScheduler
    from collectors.etherscan_collector import EtherscanCollector
    from collectors.whale_alert_collector import WhaleAlertCollector
    from collectors.defillama_collector import DefiLlamaCollector
    from collectors.coingecko_collector import CoinGeckoCollector
    from alerts.engine import evaluate_all_rules

    collector = EtherscanCollector()
    whale_collector = WhaleAlertCollector()
    defillama_collector = DefiLlamaCollector()
    coingecko_collector = CoinGeckoCollector()

    def _run_collection():
        """Core collection + alert evaluation."""
        from database.connection import ScopedSession

        logging.info("[scheduler] Collection cycle starting")
        api_ok = bool(os.getenv("ETHERSCAN_API_KEY") or ETHERSCAN_API_KEY)
        result = {"etherscan": None, "defillama": None, "alerts": 0, "error": None, "stats": None}

        try:
            if api_ok:
                ok = collector.safe_collect()
                if ok:
                    result["etherscan"] = "success"
                    result["stats"] = copy.deepcopy(collector.last_stats)
                    try:
                        result["alerts"] = evaluate_all_rules()
                    except Exception:
                        logging.error("[scheduler] Alert evaluation failed", exc_info=True)
                else:
                    result["etherscan"] = "failed"
                    detail = getattr(collector, "last_error", None) or ""
                    result["error"] = f"Etherscan 采集失败: {detail}" if detail else "Etherscan API 调用失败，请检查 API Key 是否正确"
            else:
                result["etherscan"] = "skipped"
                result["error"] = "未配置 Etherscan API Key"

            # Supplementary collectors (best-effort)
            try:
                if defillama_collector.safe_collect():
                    result["defillama"] = "success"
            except Exception:
                logging.error("[scheduler] DeFiLlama collection failed", exc_info=True)
            try:
                whale_collector.safe_collect()
            except Exception:
                logging.error("[scheduler] Whale Alert collection failed", exc_info=True)
            try:
                coingecko_collector.safe_collect()
            except Exception:
                logging.error("[scheduler] CoinGecko collection failed", exc_info=True)

            st.session_state["last_collect_result"] = result
            st.session_state["last_collect_time"] = datetime.utcnow()
        finally:
            ScopedSession.remove()
            logging.info("[scheduler] Collection cycle finished")

    def daily_cleanup():
        from database.connection import get_session, engine, ScopedSession
        from database.models import StablecoinTransfer, WhaleMovement, MintBurnEvent, Alert, ExchangeBalanceSnapshot, PriceSnapshot
        retention = st.session_state.get("retention_days", 90)
        cutoff = datetime.utcnow() - timedelta(days=retention)
        try:
            session = get_session()
            for model in [StablecoinTransfer, WhaleMovement, MintBurnEvent, Alert, ExchangeBalanceSnapshot, PriceSnapshot]:
                deleted = session.query(model).filter(model.detected_at < cutoff).delete()
                if deleted:
                    logging.info(f"[cleanup] Deleted {deleted} old {model.__tablename__} records")
            session.commit()
        finally:
            ScopedSession.remove()
        # VACUUM needs an exclusive lock — retry if collector is mid-transaction
        for attempt in range(5):
            try:
                with engine.connect() as conn:
                    conn.exec_driver_sql("VACUUM")
                break
            except Exception as e:
                logging.warning(f"[cleanup] VACUUM attempt {attempt+1} failed: {e}")
                time.sleep(5)

    scheduler = BackgroundScheduler()
    interval = st.session_state.get("poll_interval", 120)
    # Single job: fires immediately, then every `interval` seconds.
    # max_instances=1 prevents overlap if collection takes longer than interval.
    scheduler.add_job(
        _run_collection, "interval", seconds=interval,
        next_run_time=datetime.now(),  # fire immediately on start
        id="collector_job", max_instances=1,
    )
    scheduler.add_job(daily_cleanup, "interval", hours=24, id="cleanup_job")
    scheduler.start()
    return scheduler, collector


def main():
    from database.connection import ScopedSession

    try:
        st.title("🔍 链上数据监控面板")
        st.caption("追踪链上资金流向、巨鲸动向和市场异动事件")

        # Sidebar
        render_sidebar()

        # Initialize session state
        if "scheduler" not in st.session_state:
            st.session_state["scheduler"] = None
        if "last_refresh" not in st.session_state:
            st.session_state["last_refresh"] = time.time()
        # Auto-start collector on first load
        if "collector_running" not in st.session_state:
            st.session_state["collector_running"] = True

        # Start/stop collector
        collector_started_this_run = False
        if st.session_state.get("collector_running", False):
            if st.session_state["scheduler"] is None:
                scheduler, collector = setup_scheduler()
                st.session_state["scheduler"] = scheduler
                st.session_state["collector_started_at"] = time.time()
                collector_started_this_run = True
        else:
            if st.session_state["scheduler"] is not None:
                st.session_state["scheduler"].shutdown(wait=False)
                st.session_state["scheduler"] = None

        # Status bar
        api_ok = bool(os.getenv("ETHERSCAN_API_KEY") or ETHERSCAN_API_KEY)
        running = st.session_state.get("collector_running", False)
        has_data = st.session_state.get("last_collect_time") is not None
        status_color = "🟢" if (api_ok and running and has_data) else "🟡" if (api_ok and running) else "🔴"
        status_text = "采集中" if (api_ok and running and has_data) else "启动中..." if (api_ok and running) else "需要API Key"

        # Cached counts (refreshed every 30s to avoid DB pressure on rerun)
        @st.cache_data(ttl=30)
        def _cached_alert_count():
            return get_unacknowledged_alert_count()

        @st.cache_data(ttl=30)
        def _cached_addr_count():
            return get_session().query(MonitoredAddress).filter(MonitoredAddress.is_active == True).count()

        alert_count = _cached_alert_count()
        addr_count = _cached_addr_count()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("运行状态", f"{status_color} {status_text}")
        col2.metric("未读警报", alert_count)
        col3.metric("监控地址数", addr_count)
        col4.metric("API配置", f"Etherscan: {'✓ 已配置' if api_ok else '✗ 未配置'}")

        # Show collection status (if collector is running)
        if running:
            last_result = st.session_state.get("last_collect_result")
            last_time = st.session_state.get("last_collect_time")
            if last_time:
                elapsed = (datetime.utcnow() - last_time).total_seconds()
                if last_result and last_result.get("error"):
                    st.error(f"⚠️ 采集异常: {last_result['error']}")
                elif last_result and last_result.get("etherscan") == "success":
                    stats = last_result.get("stats") or {}
                    transfers = stats.get("total_new_transfers", 0)
                    addrs = stats.get("total_addresses", 0)
                    alerts = last_result.get("alerts", 0)
                    chain_details = stats.get("chain_details", [])
                    detail_parts = [f"最近更新: {elapsed:.0f}秒前"]
                    if transfers > 0:
                        detail_parts.append(f"新增 {transfers} 笔转账")
                    else:
                        detail_parts.append(f"扫描 {addrs} 个地址无新转账")
                    if chain_details:
                        for cd in chain_details:
                            detail_parts.append(f"{cd['chain']}: {cd.get('new_transfers', 0)}笔 (区块 {cd.get('block_range', '?')})")
                    if alerts > 0:
                        detail_parts.append(f"触发 {alerts} 个警报")

                    poll_sec = st.session_state.get("poll_interval", 120)
                    if elapsed > poll_sec * 2:
                        st.warning(f"⚠️ 采集延迟: 上次采集 {elapsed:.0f} 秒前（轮询间隔 {poll_sec}秒）。采集器可能已停止，请尝试刷新页面或检查 API Key。")
                    else:
                        st.success(f"✅ 数据采集正常 ({', '.join(detail_parts)})")
                elif last_result and last_result.get("etherscan") == "failed":
                    st.error("❌ Etherscan 连接失败，请确认 API Key 有效")
                else:
                    st.info(f"⏳ 等待首次采集... ({elapsed:.0f}秒前开始)")
            else:
                st.info("⏳ 等待首次采集...")

            # Per-chain status row
            from database.queries import get_poll_state as _get_poll
            cols = st.columns(2)
            chain_labels = {"ethereum": "Ethereum", "arbitrum": "Arbitrum"}
            for i, (chain_key, label) in enumerate(chain_labels.items()):
                poll = _get_poll(f"etherscan_{chain_key}")
                with cols[i]:
                    if poll and poll.last_timestamp:
                        gap = (datetime.utcnow() - poll.last_timestamp).total_seconds()
                        if gap < 300:
                            st.caption(f"🟢 {label}: {gap:.0f}秒前 · 区块 {poll.last_block:,}")
                        elif gap < 1800:
                            st.caption(f"🟡 {label}: {gap/60:.0f}分钟前 · 区块 {poll.last_block:,}")
                        else:
                            st.caption(f"🔴 {label}: {gap/3600:.1f}小时前 · 区块 {poll.last_block:,}")
                    else:
                        st.caption(f"⚪ {label}: 暂无数据")

        st.divider()

        # Main dashboard layout
        # Row 0: Market Intelligence Brief
        render_market_intel()

        st.divider()

        # Row 1: Alerts
        render_alerts()

        st.divider()

        # Row 2: Key metrics
        render_metrics()

        st.divider()

        # Row 3: Time pattern analysis
        render_hourly_heatmap()

        st.divider()

        # Row 3.5: Price-Flow correlation
        render_price_flow_chart()

        st.divider()

        # Row 4: Exchange balance chart
        render_exchange_balance_chart()

        st.divider()

        # Row 5: Exchange flow chart + Transfer table
        col_chart, col_table = st.columns([6, 5])
        with col_chart:
            render_exchange_flow_chart()
        with col_table:
            render_transfer_table()

        st.divider()

        # Row 6: Mint/burn + Whale movements
        col_mint, col_whale = st.columns(2)
        with col_mint:
            render_mint_burn_timeline()
        with col_whale:
            render_whale_movements()

        # Auto-refresh: fast (5s) while waiting, then 30s to maintain WebSocket
        has_data = st.session_state.get("last_collect_time") is not None
        effective_interval = 30 if has_data else 5  # 30s keeps connection alive, prevents sleep
        elapsed = time.time() - st.session_state.get("last_refresh", time.time())
        next_refresh = max(0, effective_interval - elapsed)

        with st.sidebar:
            st.divider()
            if has_data:
                st.caption(f"⏱️ 下次刷新: {next_refresh:.0f}秒 · 每30秒自动保活")
            else:
                st.caption(f"⏳ 等待首次数据... ({elapsed:.0f}秒)")
            if st.button("🔄 刷新面板"):
                st.session_state["last_refresh"] = time.time()
                st.rerun()

        # Auto-refresh to keep WebSocket alive and prevent Streamlit Cloud sleep
        if next_refresh <= 0:
            st.session_state["last_refresh"] = time.time()
            time.sleep(0.3)
            st.rerun()
    finally:
        ScopedSession.remove()


if __name__ == "__main__":
    main()
