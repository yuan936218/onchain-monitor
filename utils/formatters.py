"""Number formatting utilities for dashboard display."""


def format_usd(value: float | None) -> str:
    """Format a USD value in human-readable form."""
    if value is None:
        return "-"
    v = abs(value)
    if v >= 1_000_000_000:
        return f"${value/1_000_000_000:.2f}B"
    elif v >= 1_000_000:
        return f"${value/1_000_000:.2f}M"
    elif v >= 1_000:
        return f"${value/1_000:.2f}K"
    else:
        return f"${value:.2f}"


def format_token_amount(value: float, symbol: str) -> str:
    """Format a token amount in human-readable form."""
    if value >= 1_000_000:
        return f"{value/1_000_000:.2f}M {symbol}"
    elif value >= 1_000:
        return f"{value/1_000:.2f}K {symbol}"
    else:
        return f"{value:,.2f} {symbol}"


def format_address(address: str, length: int = 6) -> str:
    """Shorten an address to 0x1234...abcd format."""
    if len(address) <= length * 2 + 2:
        return address
    return f"{address[:length]}...{address[-4:]}"


def format_timestamp(ts) -> str:
    """Format timestamp for display."""
    if ts is None:
        return "-"
    return ts.strftime("%Y-%m-%d %H:%M UTC")
