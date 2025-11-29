import os
import json
import duckdb
from pathlib import Path
from datetime import datetime


def path_for_store(filename="offline_store.duckdb"):
    """Return absolute path for the offline DuckDB store inside backend/feature_repo."""
    base = Path(__file__).resolve().parents[1]
    store_dir = base
    store_dir.mkdir(parents=True, exist_ok=True)
    return str(store_dir / filename)


def connect(path=None):
    """Connect to DuckDB file. If path not provided, uses default offline_store.duckdb."""
    if path is None:
        path = path_for_store()
    # duckdb.connect will create the file if it doesn't exist
    con = duckdb.connect(database=path)
    return con


def execute(sql, params=None, path=None):
    """Execute SQL against the duckdb offline store and return results."""
    con = connect(path)
    if params:
        cur = con.execute(sql, params)
    else:
        cur = con.execute(sql)
    try:
        rows = cur.fetchall()
    except Exception:
        rows = None
    con.close()
    return rows


def ensure_feature_values_table(path=None):
    """Create a `feature_values` table if it doesn't exist.

    Columns:
      - feature TEXT
      - pricing_data_id BIGINT NULL
      - node_id TEXT NULL
      - value DOUBLE NULL
      - raw_value JSON NULL
      - computed_at TIMESTAMP
    """
    con = connect(path)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS feature_values (
            feature TEXT,
            pricing_data_id BIGINT,
            node_id TEXT,
            value DOUBLE,
            raw_value JSON,
            computed_at TIMESTAMP
        )
        """
    )
    con.close()


def insert_feature_values(rows, path=None):
    """Insert a list of feature value dicts into the feature_values table.

    Each row should be a dict with keys: feature, pricing_data_id, node_id, value, raw_value, computed_at
    """
    if not rows:
        return 0
    con = connect(path)
    # Prepare rows for insertion
    prepared = []
    for r in rows:
        prepared.append((
            r.get('feature'),
            r.get('pricing_data_id'),
            r.get('node_id'),
            float(r['value']) if r.get('value') is not None else None,
            json.dumps(r.get('raw_value') or {}),
            r.get('computed_at') or datetime.utcnow()
        ))

    # Some DuckDB builds don't expose PARSE_JSON; pass the JSON string directly
    # into the JSON column and let DuckDB coerce it if supported.
    con.executemany("INSERT INTO feature_values VALUES (?, ?, ?, ?, ?, ?)", prepared)
    con.close()
    return len(prepared)
