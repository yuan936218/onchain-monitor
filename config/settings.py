"""Application settings loaded from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()

# HTTP Proxy (needed in China to access blockchain APIs)
HTTP_PROXY = os.getenv("HTTP_PROXY", os.getenv("http_proxy", ""))
HTTPS_PROXY = os.getenv("HTTPS_PROXY", os.getenv("https_proxy", ""))

# Custom Etherscan API base URL (use Cloudflare Worker proxy for China users)
# Leave empty to use official api.etherscan.io
ETHERSCAN_BASE_URL = os.getenv("ETHERSCAN_BASE_URL", "https://api.etherscan.io")

# Feishu bot webhook URL
FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL", "")

# API Keys
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")
WHALE_ALERT_API_KEY = os.getenv("WHALE_ALERT_API_KEY", "")

# Alert thresholds (in USD)
THRESHOLD_LARGE_TRANSFER = float(os.getenv("THRESHOLD_LARGE_TRANSFER", "1000000"))       # $1M
THRESHOLD_EXCHANGE_INFLOW = float(os.getenv("THRESHOLD_EXCHANGE_INFLOW", "5000000"))      # $5M single tx
THRESHOLD_EXCHANGE_FLOW_SURGE = float(os.getenv("THRESHOLD_EXCHANGE_FLOW_SURGE", "50000000"))  # $50M in 10min
THRESHOLD_WHALE_MOVE = float(os.getenv("THRESHOLD_WHALE_MOVE", "500000"))                 # $500K

# Polling
DEFAULT_POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL", "120"))

# Data retention (days)
DATA_RETENTION_DAYS = int(os.getenv("DATA_RETENTION_DAYS", "90"))

# Stablecoin contract addresses (Ethereum mainnet)
STABLECOIN_TOKENS = {
    "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
}

# Tether/USDC issuer addresses (for mint/burn detection)
STABLECOIN_ISSUERS = {
    "USDT": "0xC6CDE7C39eB2f0F0095F41570af89eFC2C1Ea828",  # Tether Treasury
    "USDC": "0x55FE002aefF02F77364de339a1292923A15844B8",  # Circle Mint
}
