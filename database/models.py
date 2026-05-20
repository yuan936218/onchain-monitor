"""SQLAlchemy ORM models for on-chain monitoring."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, Text, UniqueConstraint, Index
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class MonitoredAddress(Base):
    __tablename__ = "monitored_addresses"
    __table_args__ = (UniqueConstraint("address", "chain", name="uq_address_chain"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    address = Column(String(42), nullable=False)
    label = Column(String(100), nullable=False)
    category = Column(String(20), nullable=False)  # exchange, whale, contract, personal
    chain = Column(String(20), nullable=False, default="ethereum")
    is_active = Column(Boolean, nullable=False, default=True)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StablecoinTransfer(Base):
    __tablename__ = "stablecoin_transfers"
    __table_args__ = (
        UniqueConstraint("tx_hash", "token_symbol", name="uq_tx_token"),
        Index("idx_st_timestamp", "block_timestamp"),
        Index("idx_st_value_usd", "value_usd"),
        Index("idx_st_to_label", "to_label"),
        Index("idx_st_from_label", "from_label"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    tx_hash = Column(String(66), nullable=False)
    chain = Column(String(20), nullable=False, default="ethereum")
    token_symbol = Column(String(10), nullable=False)
    token_address = Column(String(42), nullable=False)
    from_address = Column(String(42), nullable=False)
    to_address = Column(String(42), nullable=False)
    from_label = Column(String(100))
    to_label = Column(String(100))
    value = Column(Float, nullable=False)
    value_usd = Column(Float)
    block_number = Column(Integer, nullable=False)
    block_timestamp = Column(DateTime, nullable=False)
    gas_used = Column(Integer)
    gas_price_gwei = Column(Float)
    detected_at = Column(DateTime, default=datetime.utcnow)


class WhaleMovement(Base):
    __tablename__ = "whale_movements"
    __table_args__ = (
        Index("idx_wm_timestamp", "block_timestamp"),
        Index("idx_wm_value_usd", "value_usd"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    tx_hash = Column(String(66), nullable=False, unique=True)
    chain = Column(String(20), nullable=False, default="ethereum")
    from_address = Column(String(42), nullable=False)
    to_address = Column(String(42), nullable=False)
    from_label = Column(String(100))
    to_label = Column(String(100))
    asset = Column(String(10), nullable=False)
    value = Column(Float, nullable=False)
    value_usd = Column(Float)
    block_number = Column(Integer, nullable=False)
    block_timestamp = Column(DateTime, nullable=False)
    detected_at = Column(DateTime, default=datetime.utcnow)


class MintBurnEvent(Base):
    __tablename__ = "mint_burn_events"
    __table_args__ = (Index("idx_mb_timestamp", "block_timestamp"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    tx_hash = Column(String(66), nullable=False, unique=True)
    chain = Column(String(20), nullable=False, default="ethereum")
    token_symbol = Column(String(10), nullable=False)
    token_address = Column(String(42), nullable=False)
    event_type = Column(String(10), nullable=False)  # mint or burn
    value = Column(Float, nullable=False)
    value_usd = Column(Float)
    block_number = Column(Integer, nullable=False)
    block_timestamp = Column(DateTime, nullable=False)
    detected_at = Column(DateTime, default=datetime.utcnow)


class ExchangeBalanceSnapshot(Base):
    __tablename__ = "exchange_balance_snapshots"
    __table_args__ = (
        Index("idx_ebs_snapshot_at", "snapshot_at"),
        Index("idx_ebs_exchange", "exchange_name"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    chain = Column(String(20), nullable=False, default="ethereum")
    exchange_name = Column(String(100), nullable=False)
    exchange_address = Column(String(42), nullable=False)
    token_symbol = Column(String(10), nullable=False)
    token_address = Column(String(42), nullable=False)
    balance_raw = Column(Float, nullable=False)
    balance_usd = Column(Float)
    snapshot_at = Column(DateTime, nullable=False)
    detected_at = Column(DateTime, default=datetime.utcnow)


class DailyAggregate(Base):
    __tablename__ = "daily_aggregates"
    __table_args__ = (UniqueConstraint("date", "chain", "metric_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    chain = Column(String(20), nullable=False, default="ethereum")
    metric_name = Column(String(50), nullable=False)
    value = Column(Float, nullable=False)


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("idx_alerts_created", "created_at"),
        Index("idx_alerts_acknowledged", "is_acknowledged"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_type = Column(String(30), nullable=False)
    severity = Column(String(10), nullable=False, default="info")  # info, warning, critical
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    related_tx_hash = Column(String(66))
    chain = Column(String(20), nullable=True)
    value_usd = Column(Float)
    is_acknowledged = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class PollState(Base):
    __tablename__ = "poll_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False, unique=True)
    last_block = Column(Integer, nullable=False)
    last_timestamp = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
