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

# Stablecoin contract addresses
STABLECOIN_TOKENS = {
    "ethereum": {
        "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    },
    "arbitrum": {
        "USDT": "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9",
        "USDC": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
    },
    "bsc": {
        "USDT": "0x55d398326f99059fF775485246999027B3197955",
        "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
    },
}

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


def get_tokens_for_chain(chain: str) -> dict:
    """Get stablecoin token addresses for a specific chain."""
    return STABLECOIN_TOKENS.get(chain, {})
