# On-Chain Monitor — Project Memory

## Deployment
- **Streamlit Cloud**: `https://onchain-monitor-svt7nszxst3gincc48tv9x.streamlit.app/`
- **GitHub**: `git@github.com:yuan936218/onchain-monitor.git` (SSH, not HTTPS — avoids GFW blocking)
- **SSH key**: `~/.ssh/id_ed25519` (registered on GitHub for yuan936218)

## Critical bugs fixed (2026-05-20)
1. **All dashboard panels showed empty** while alerts worked — dashboard queries filtered by `block_timestamp` (blockchain time, up to 16 days old for historical blocks scanned during initial collection), while alerts used `detected_at` (when we collected the data). Fixed in `database/queries.py` — all time filters now use `detected_at`.
2. **Sidebar threshold sliders didn't affect alert rules** — sidebar wrote to `st.session_state` but `alerts/rules.py` read module-level constants. Fixed: rules now call `_get_threshold()` which reads from `st.session_state` with fallback.
3. **Initial scan range was 500 blocks** (too narrow, ~2 hours). Changed to 10,000 blocks (~1.5 days) in `collectors/etherscan_collector.py`.
4. **First collection ran in background thread only** — errors were invisible. Fixed: `setup_scheduler()` runs one synchronous `collect()` before starting APScheduler.
5. **Daily cleanup used `block_timestamp` for retention** — would delete recently-collected historical data. Fixed to use `detected_at`.
6. **`daily_cleanup` used raw `sqlite3.connect` for VACUUM** — conflicts with SQLAlchemy engine. Fixed to use `engine.connect().exec_driver_sql("VACUUM")`.
7. **`large_tx_count` was inside `if exchange_addrs:` block** in `get_24h_aggregates()` — wouldn't count large txs when 0 exchange addresses. Fixed.
8. **`resolve_label` had `@lru_cache`** — thread-safety issue with SQLAlchemy sessions. Replaced with plain dict cache.

## Latest changes (2026-05-20, commit 9631e1a)
9. **Mint/burn auto-detection** — collector detects mint (from 0x0000...0) and burn (to 0x0000...0) in the same transfer loop, creates `MintBurnEvent` records immediately.
10. **Whale panel fallback** — when `WhaleMovement` table is empty, the whale panel falls back to querying `StablecoinTransfer` for transfers >$10M (72h window) as inferred whale activity.
11. **Sidebar redesigned** — removed manual start/stop button. Replaced with small pause/resume toggle at top, status indicator (🟢 运行中 / ⏸️ 已暂停), test & diagnostic buttons side by side. Footer: "链上监控 v1.0 · 自动采集".

## Architecture key points
- **Etherscan V2 API** requires `chainid=1` param and `/v2/api` URL path (NOT `/api`)
- **`account/tokentx`** is the endpoint the collector uses (different from `account/txlist` used by the test button)
- **Whale detection** now works without Whale Alert API key — the etherscan collector checks if transfers involve whale addresses from `config/addresses.json` and creates `WhaleMovement` records
- **Session management**: `ScopedSession` is thread-local — collector and dashboard share the same session in main thread, background scheduler gets its own. Do NOT call `session.remove()` in shared helper functions.

## User preferences
- All UI in **Chinese**
- Notifications via **Feishu (飞书)** webhook, NOT Telegram
- User is a crypto futures trader, not a developer ("我不懂代码")
- User is in China — GitHub HTTPS often blocked by GFW, use SSH
- Claude must respond in **Chinese only** at all times
