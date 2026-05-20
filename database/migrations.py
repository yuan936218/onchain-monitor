"""Auto-create and migrate database tables on startup."""

import logging
from sqlalchemy import inspect, text
from database.models import Base
from database.connection import engine

logger = logging.getLogger(__name__)


def _migrate_monitored_addresses():
    """Rebuild monitored_addresses if it still has the old unique-address-only constraint."""
    inspector = inspect(engine)
    if "monitored_addresses" not in inspector.get_table_names():
        return

    # Check if the new composite unique constraint already exists
    existing_columns = inspector.get_columns("monitored_addresses")
    has_chain_col = any(c["name"] == "chain" for c in existing_columns)

    unique_constraints = inspector.get_unique_constraints("monitored_addresses")
    has_new_constraint = any("uq_address_chain" in (uc.get("name") or "") for uc in unique_constraints)

    if has_chain_col and has_new_constraint:
        return  # Already migrated

    logger.info("[migration] Rebuilding monitored_addresses for multi-chain support")

    with engine.connect() as conn:
        # Copy data out
        result = conn.execute(text("SELECT * FROM monitored_addresses"))
        rows = [dict(row._mapping) for row in result]

        # Drop old table
        conn.execute(text("DROP TABLE monitored_addresses"))
        conn.commit()

    # Recreate with new schema
    Base.metadata.create_all(engine, tables=[Base.metadata.tables["monitored_addresses"]])

    # Restore data
    if rows:
        with engine.connect() as conn:
            for row in rows:
                # Remove 'id' to let autoincrement assign new ones
                row.pop("id", None)
                row.setdefault("chain", "ethereum")
                columns = ", ".join(row.keys())
                placeholders = ", ".join(f":{k}" for k in row)
                conn.execute(
                    text(f"INSERT INTO monitored_addresses ({columns}) VALUES ({placeholders})"),
                    row,
                )
            conn.commit()

    logger.info(f"[migration] Rebuilt monitored_addresses, restored {len(rows)} rows")


def _migrate_alerts_add_chain():
    """Add chain column to alerts table if missing."""
    inspector = inspect(engine)
    if "alerts" not in inspector.get_table_names():
        return

    existing_columns = inspector.get_columns("alerts")
    has_chain_col = any(c["name"] == "chain" for c in existing_columns)

    if has_chain_col:
        return

    logger.info("[migration] Adding chain column to alerts")
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE alerts ADD COLUMN chain VARCHAR(20)"))
        conn.commit()


def init_database():
    Base.metadata.create_all(engine)
    _migrate_monitored_addresses()
    _migrate_alerts_add_chain()
