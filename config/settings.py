"""Application settings — reads from env, .env file, and Streamlit Cloud secrets."""

import os
from dotenv import load_dotenv

load_dotenv()


def _get_config(key: str, default: str = "") -> str:
    """Get config value from Streamlit secrets, env var, or default (in that order)."""
    # Try Streamlit Cloud secrets first
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    # Fall back to env var / .env file
    return os.getenv(key, default)


# HTTP Proxy
HTTP_PROXY = _get_config("HTTP_PROXY", os.getenv("http_proxy", ""))
HTTPS_PROXY = _get_config("HTTPS_PROXY", os.getenv("https_proxy", ""))

# Etherscan API
ETHERSCAN_BASE_URL = _get_config("ETHERSCAN_BASE_URL", "https://api.etherscan.io/v2/api")

# Feishu bot webhook
FEISHU_WEBHOOK_URL = _get_config("FEISHU_WEBHOOK_URL", "")

# API Keys
ETHERSCAN_API_KEY = _get_config("ETHERSCAN_API_KEY", "")
WHALE_ALERT_API_KEY = _get_config("WHALE_ALERT_API_KEY", "")

# Alert thresholds (in USD)
THRESHOLD_LARGE_TRANSFER = float(_get_config("THRESHOLD_LARGE_TRANSFER", "10000000"))
THRESHOLD_EXCHANGE_INFLOW = float(_get_config("THRESHOLD_EXCHANGE_INFLOW", "5000000"))
THRESHOLD_EXCHANGE_FLOW_SURGE = float(_get_config("THRESHOLD_EXCHANGE_FLOW_SURGE", "50000000"))
THRESHOLD_WHALE_MOVE = float(_get_config("THRESHOLD_WHALE_MOVE", "500000"))

# Polling
DEFAULT_POLL_INTERVAL_SECONDS = int(_get_config("POLL_INTERVAL", "120"))

# Data retention (days)
DATA_RETENTION_DAYS = int(_get_config("DATA_RETENTION_DAYS", "90"))

# Monitored tokens (ERC-20 + native ETH)
# type: "erc20" = ERC-20 token tracked via tokentx, "native" = native coin via txlist
MONITORED_TOKENS = {
    "ethereum": {
        "USDT": {"address": "0xdAC17F958D2ee523a2206206994597C13D831ec7", "type": "erc20", "coingecko_id": "tether", "decimals": 6},
        "USDC": {"address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "type": "erc20", "coingecko_id": "usd-coin", "decimals": 6},
        "ETH":  {"type": "native", "coingecko_id": "ethereum", "decimals": 18},
        "WBTC": {"address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599", "type": "erc20", "coingecko_id": "wrapped-bitcoin", "decimals": 8},
    },
    "arbitrum": {
        "USDT": {"address": "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9", "type": "erc20", "coingecko_id": "tether", "decimals": 6},
        "USDC": {"address": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831", "type": "erc20", "coingecko_id": "usd-coin", "decimals": 6},
        "ETH":  {"type": "native", "coingecko_id": "ethereum", "decimals": 18},
        "WBTC": {"address": "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f", "type": "erc20", "coingecko_id": "wrapped-bitcoin", "decimals": 8},
    },
    "bsc": {
        "USDT": {"address": "0x55d398326f99059fF775485246999027B3197955", "type": "erc20", "coingecko_id": "tether", "decimals": 18},
        "USDC": {"address": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d", "type": "erc20", "coingecko_id": "usd-coin", "decimals": 18},
        "ETH":  {"address": "0x2170Ed0880ac9A755fd29B2688956BD959F933F8", "type": "erc20", "coingecko_id": "ethereum", "decimals": 18},
        "WBTC": {"address": "0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c", "type": "erc20", "coingecko_id": "wrapped-bitcoin", "decimals": 18},
    },
}

# Deprecated alias for backward compatibility
STABLECOIN_TOKENS = MONITORED_TOKENS

STABLECOIN_ISSUERS = {
    "ethereum": {
        "USDT": "0xC6CDE7C39eB2f0F0095F41570af89eFC2C1Ea828",
        "USDC": "0x55FE002aefF02F77364de339a1292923A15844B8",
    },
    "arbitrum": {
        "USDT": "0xC6CDE7C39eB2f0F0095F41570af89eFC2C1Ea828",
        "USDC": "0x55FE002aefF02F77364de339a1292923A15844B8",
    },
    "bsc": {
        "USDT": "0xC6CDE7C39eB2f0F0095F41570af89eFC2C1Ea828",
        "USDC": "0x55FE002aefF02F77364de339a1292923A15844B8",
    },
}

CHAIN_CONFIG = {
    "ethereum": {"chain_id": "1", "explorer": "https://etherscan.io", "label": "Ethereum"},
    "arbitrum": {"chain_id": "42161", "explorer": "https://arbiscan.io", "label": "Arbitrum"},
    "bsc": {"chain_id": "56", "explorer": "https://bscscan.com", "label": "BSC"},
}

TOKEN_LIST = ["USDT", "USDC", "ETH", "WBTC"]


def get_tokens_for_chain(chain: str) -> dict:
    """Get ERC-20 token addresses for a specific chain (backward compat)."""
    tokens = MONITORED_TOKENS.get(chain, {})
    return {sym: info["address"] for sym, info in tokens.items()
            if info.get("type") == "erc20" and info.get("address")}
