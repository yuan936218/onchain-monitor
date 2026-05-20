"""On-Chain Data Monitoring Dashboard — Main Entry Point."""

import json
import sys
import os
import time
import logging
from datetime import datetime, timedelta
from threading import Lock

sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd

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

logging.basicConfig(level=logging.INFO)

# Initialize database
init_database()


def seed_addresses():
    """Seed monitored_addresses table from config/addresses.json."""
    session = get_session()

    config_path = os.path.join(os.path.dirname(__file__), "config", "addresses.json")
    with open(config_path, "r") as f:
        data = json.load(f)

    seeded = 0
    for chain, categories in data.items():
        for category, addresses in categories.items():
            for addr in addresses:
                exists = session.query(MonitoredAddress).filter(
                    MonitoredAddress.address == addr["address"].lower()
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
    if seeded > 0:
        return seeded
    return 0


# Seed on first run
seed_addresses()


def setup_scheduler(run_sync_first=True):
    """Configure and start the APScheduler background collectors."""
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

    # Run one synchronous collection first to surface any errors immediately
    if run_sync_first:
        api_ok = bool(os.getenv("ETHERSCAN_API_KEY") or ETHERSCAN_API_KEY)
        result = {"etherscan": None, "defillama": None, "alerts": 0, "error": None, "stats": None}
        if api_ok:
            try:
                collector.collect()
                result["etherscan"] = "success"
                result["stats"] = collector.last_stats
                result["alerts"] = evaluate_all_rules()
                st.session_state["last_collect_result"] = result
                st.session_state["last_collect_time"] = datetime.utcnow()
            except Exception as e:
                import traceback
                traceback.print_exc()
                result["etherscan"] = "failed"
                result["error"] = f"采集异常: {str(e)[:500]}"
                result["stats"] = collector.last_stats
                st.session_state["last_collect_result"] = result
                st.session_state["last_collect_time"] = datetime.utcnow()
        else:
            result["etherscan"] = "skipped"
            result["error"] = "未配置 Etherscan API Key，请在侧边栏输入"
            st.session_state["last_collect_result"] = result
            st.session_state["last_collect_time"] = datetime.utcnow()

        # Run other collectors
        try:
            if defillama_collector.safe_collect():
                result["defillama"] = "success"
        except Exception:
            pass
        try:
            whale_collector.safe_collect()
        except Exception:
            pass
        try:
            coingecko_collector.safe_collect()
        except Exception:
            pass

    def collect_all():
        api_ok = bool(os.getenv("ETHERSCAN_API_KEY") or ETHERSCAN_API_KEY)
        result = {"etherscan": None, "defillama": None, "alerts": 0, "error": None, "stats": None}
        if api_ok:
            ok = collector.safe_collect()
            if ok:
                result["etherscan"] = "success"
                result["stats"] = collector.last_stats
                result["alerts"] = evaluate_all_rules()
            else:
                result["etherscan"] = "failed"
                result["error"] = "Etherscan API 调用失败，请检查 API Key 是否正确"
        else:
            result["etherscan"] = "skipped"
            result["error"] = "未配置 Etherscan API Key，请在侧边栏输入"
        if defillama_collector.safe_collect():
            result["defillama"] = "success"
        whale_collector.safe_collect()
        coingecko_collector.safe_collect()
        st.session_state["last_collect_result"] = result
        st.session_state["last_collect_time"] = datetime.utcnow()

    def daily_cleanup():
        from database.connection import get_session
        from database.models import StablecoinTransfer, WhaleMovement, MintBurnEvent, Alert
        retention = st.session_state.get("retention_days", 90)
        cutoff = datetime.utcnow() - timedelta(days=retention)
        session = get_session()
        for model in [StablecoinTransfer, WhaleMovement, MintBurnEvent, Alert]:
            deleted = session.query(model).filter(model.block_timestamp < cutoff).delete()
            if deleted:
                logging.info(f"[cleanup] Deleted {deleted} old {model.__tablename__} records")
        session.commit()
        # Vacuum to reclaim disk space
        from database.connection import engine
        import sqlite3
        db_path = os.path.join(os.path.dirname(__file__), "data", "onchain_monitor.db")
        conn = sqlite3.connect(db_path)
        conn.execute("VACUUM")
        conn.close()

    scheduler = BackgroundScheduler()
    interval = st.session_state.get("poll_interval", 120)
    scheduler.add_job(collect_all, "interval", seconds=interval, id="collector_job")
    scheduler.add_job(daily_cleanup, "interval", hours=24, id="cleanup_job")
    scheduler.start()
    return scheduler, collector


def main():
    st.title("🔍 链上数据监控面板")
    st.caption("追踪稳定币流向、巨鲸动向和市场异动事件")

    # Sidebar
    render_sidebar()

    # Initialize session state
    if "scheduler" not in st.session_state:
        st.session_state["scheduler"] = None
    if "last_refresh" not in st.session_state:
        st.session_state["last_refresh"] = time.time()

    # Start/stop collector
    if st.session_state.get("collector_running", False):
        if st.session_state["scheduler"] is None:
            scheduler, collector = setup_scheduler()
            st.session_state["scheduler"] = scheduler
            st.toast("✅ 数据采集已启动!")
    else:
        if st.session_state["scheduler"] is not None:
            st.session_state["scheduler"].shutdown(wait=False)
            st.session_state["scheduler"] = None
            st.toast("⏸️ 数据采集已停止")

    # Status bar
    api_ok = bool(os.getenv("ETHERSCAN_API_KEY") or ETHERSCAN_API_KEY)
    running = st.session_state.get("collector_running", False)
    status_color = "🟢" if (api_ok and running) else "🟡" if api_ok else "🔴"
    status_text = "采集中" if (api_ok and running) else "就绪 (API已配置)" if api_ok else "需要API Key"

    alert_count = get_unacknowledged_alert_count()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("运行状态", f"{status_color} {status_text}")
    col2.metric("未读警报", alert_count)
    col3.metric("监控地址数", get_session().query(MonitoredAddress).filter(MonitoredAddress.is_active == True).count())
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
                transfers = stats.get("new_transfers", 0)
                blocks = stats.get("block_range", "?")
                addrs = stats.get("addresses", 0)
                alerts = last_result.get("alerts", 0)
                detail_parts = [f"最近更新: {elapsed:.0f}秒前"]
                if transfers > 0:
                    detail_parts.append(f"新增 {transfers} 笔转账")
                else:
                    detail_parts.append(f"扫描 {addrs} 个地址无新转账 (区块 {blocks})")
                if alerts > 0:
                    detail_parts.append(f"触发 {alerts} 个警报")
                st.success(f"✅ 数据采集正常 ({', '.join(detail_parts)})")
            elif last_result and last_result.get("etherscan") == "failed":
                st.error(f"❌ Etherscan 连接失败，请确认 API Key 有效")
            else:
                st.info(f"⏳ 等待首次采集... ({elapsed:.0f}秒前开始)")
        else:
            st.info("⏳ 等待首次采集...")

    st.divider()

    # Main dashboard layout
    # Row 1: Alerts
    render_alerts()

    st.divider()

    # Row 2: Key metrics
    render_metrics()

    st.divider()

    # Row 3: Exchange flow chart + Transfer table
    col_chart, col_table = st.columns([6, 5])
    with col_chart:
        render_exchange_flow_chart()
    with col_table:
        render_transfer_table()

    st.divider()

    # Row 4: Mint/burn + Whale movements
    col_mint, col_whale = st.columns(2)
    with col_mint:
        render_mint_burn_timeline()
    with col_whale:
        render_whale_movements()

    # Auto-refresh countdown
    poll_interval = st.session_state.get("poll_interval", 120)
    elapsed = time.time() - st.session_state.get("last_refresh", time.time())
    next_refresh = max(0, poll_interval - elapsed)

    with st.sidebar:
        st.divider()
        st.caption(f"下次自动刷新: {next_refresh:.0f}秒")
        if st.button("🔄 刷新面板"):
            st.session_state["last_refresh"] = time.time()
            st.rerun()

    # Auto-refresh if collector is running
    if running and next_refresh <= 0:
        st.session_state["last_refresh"] = time.time()
        time.sleep(0.5)
        st.rerun()

    # Periodic refresh if collector is not running
    if not running:
        time.sleep(poll_interval)
        st.rerun()


if __name__ == "__main__":
    main()
