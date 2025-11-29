"""Feature repo helpers for offline DuckDB store.

This module contains a small DuckDB helper
to materialize or query the offline feature store.
"""

from .duckdb_client import connect, execute, path_for_store

__all__ = ["connect", "execute", "path_for_store"]
