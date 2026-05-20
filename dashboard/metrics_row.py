"""Key metrics row component — Chinese UI."""

import streamlit as st
from database.queries import get_24h_aggregates
from utils.formatters import format_usd


def render_metrics():
    st.subheader("📊 关键指标 (最近24小时)")

    # ── Debug: show actual database state ──
    with st.expander("🔧 数据库诊断", expanded=False):
        from database.connection import get_session
        from database.models import StablecoinTransfer, Alert, MonitoredAddress
        from sqlalchemy import func
        s = get_session()
        total_tx = s.query(func.count(StablecoinTransfer.id)).scalar()
        total_alerts = s.query(func.count(Alert.id)).scalar()
        total_addrs = s.query(func.count(MonitoredAddress.id)).filter(MonitoredAddress.is_active == True).scalar()
        exchange_addrs = s.query(MonitoredAddress.address).filter(
            MonitoredAddress.category == "exchange", MonitoredAddress.is_active == True
        ).all()
        exchange_addrs_list = [a[0] for a in exchange_addrs]

        st.caption(f"数据库: {total_tx} 笔转账 | {total_alerts} 条警报 | {total_addrs} 个监控地址 (其中 {len(exchange_addrs_list)} 个交易所)")

        if total_tx > 0:
            # Show most recent transfers
            latest = s.query(StablecoinTransfer).order_by(StablecoinTransfer.detected_at.desc()).limit(5).all()
            st.caption("最近5笔转账:")
            for t in latest:
                st.caption(
                    f"  {t.token_symbol} {t.value:,.2f} | "
                    f"from={t.from_address[:10]}... to={t.to_address[:10]}... | "
                    f"from_label={t.from_label} to_label={t.to_label} | "
                    f"block={t.block_number} ts={t.block_timestamp} | "
                    f"detected={t.detected_at}"
                )

            # Check if exchange addresses match
            if exchange_addrs_list:
                sample_exchange = exchange_addrs_list[0]
                count_to_exchange = s.query(func.count(StablecoinTransfer.id)).filter(
                    StablecoinTransfer.to_address == sample_exchange
                ).scalar()
                st.caption(f"示例: 转入 {sample_exchange[:10]}... 的交易数 = {count_to_exchange}")

        if total_tx == 0 and total_alerts > 0:
            st.warning("⚠️ 异常: 警报存在但转账记录为空！请检查采集器日志。")

    agg = get_24h_aggregates()

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            label="总流入",
            value=format_usd(agg["inflow"]),
            help="流入交易所钱包的稳定币总价值",
        )

    with col2:
        st.metric(
            label="总流出",
            value=format_usd(agg["outflow"]),
            help="流出交易所钱包的稳定币总价值",
        )

    with col3:
        net = agg["net_flow"]
        delta = f"{'+' if net > 0 else ''}{format_usd(net)}"
        st.metric(
            label="净流向",
            value=format_usd(abs(net)),
            delta=delta,
            delta_color="normal" if net > 0 else "inverse",
            help="正值 = 资金流出交易所(囤币信号)\n负值 = 资金流入交易所(潜在抛压)",
        )

    with col4:
        st.metric(
            label="大额转账 (>$1M)",
            value=agg["large_tx_count"],
        )

    with col5:
        st.metric(
            label="铸造事件",
            value=agg["mint_count"],
            help="稳定币新铸造次数",
        )
