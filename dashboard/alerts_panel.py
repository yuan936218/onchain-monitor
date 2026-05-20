"""Alert banner component — Chinese UI."""

import streamlit as st
from database.queries import get_recent_alerts, acknowledge_alert
from utils.formatters import format_timestamp, format_usd, get_explorer_tx_url


def render_alerts():
    st.subheader("🔔 警报")

    alerts = get_recent_alerts(limit=20)
    unacknowledged = [a for a in alerts if not a.is_acknowledged]

    if unacknowledged:
        st.caption(f"{len(unacknowledged)} 条未读警报")

    if not alerts:
        st.info("暂无警报。当检测到大额链上异动时会自动推送警报。")
        return

    for alert in alerts:
        severity_config = {
            "critical": {"color": "red", "label": "严重", "icon": "🔴"},
            "warning": {"color": "orange", "label": "警告", "icon": "🟡"},
            "info": {"color": "blue", "label": "提示", "icon": "🔵"},
        }
        cfg = severity_config.get(alert.severity, {"color": "grey", "label": alert.severity, "icon": "⚪"})

        with st.container():
            col1, col2, col3 = st.columns([10, 1, 1])
            with col1:
                st.markdown(f"**:{cfg['color']}[{cfg['label']}]** {alert.title}")
                st.caption(alert.description)
                val_text = format_usd(alert.value_usd) if alert.value_usd else ""
                st.caption(f"{val_text} — {format_timestamp(alert.created_at)}")
            with col2:
                if alert.related_tx_hash:
                    tx_url = get_explorer_tx_url(alert.chain or "ethereum", alert.related_tx_hash)
                    st.link_button("↗ 查看", tx_url)
            with col3:
                if not alert.is_acknowledged:
                    if st.button("✓", key=f"ack_{alert.id}", help="标记已读"):
                        acknowledge_alert(alert.id)
                        st.rerun()
            st.divider()
