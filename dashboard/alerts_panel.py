"""Alert banner component."""

import streamlit as st
from database.queries import get_recent_alerts, acknowledge_alert
from utils.formatters import format_timestamp, format_usd


def render_alerts():
    st.subheader("🔔 Alerts")

    alerts = get_recent_alerts(limit=20)
    unacknowledged = [a for a in alerts if not a.is_acknowledged]

    if unacknowledged:
        st.caption(f"{len(unacknowledged)} unacknowledged alert(s)")

    if not alerts:
        st.info("No alerts yet. Alerts appear when large on-chain movements are detected.")
        return

    for alert in alerts:
        severity_color = {
            "critical": "red",
            "warning": "orange",
            "info": "blue",
        }.get(alert.severity, "grey")

        with st.container():
            col1, col2, col3 = st.columns([10, 1, 1])
            with col1:
                st.markdown(
                    f"**:{severity_color}[{alert.severity.upper()}]** {alert.title}"
                )
                st.caption(alert.description)
                val_text = format_usd(alert.value_usd) if alert.value_usd else ""
                st.caption(f"{val_text} — {format_timestamp(alert.created_at)}")
            with col2:
                if alert.related_tx_hash:
                    tx_url = f"https://etherscan.io/tx/{alert.related_tx_hash}"
                    st.link_button("↗ TX", tx_url)
            with col3:
                if not alert.is_acknowledged:
                    if st.button("✓", key=f"ack_{alert.id}", help="Acknowledge"):
                        acknowledge_alert(alert.id)
                        st.rerun()
            st.divider()
