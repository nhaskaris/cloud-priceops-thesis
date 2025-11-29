import os
import json
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def get_redis_url():
    return os.getenv('REDIS_URL', 'redis://redis:6379/0')


def _write_to_redis(rows: List[Dict]):
    """Fallback writer: write feature values to Redis under simple keys.

    Key format: features:{feature_name}:{pricing_data_id}
    Value: JSON string {value:..., raw_value:..., computed_at:...}
    """
    try:
        import redis
    except Exception:
        logger.exception('redis package not available for fallback online write')
        return 0

    url = get_redis_url()
    r = redis.from_url(url)
    written = 0
    for row in rows:
        pricing_id = row.get('pricing_data_id')
        node_id = row.get('node_id')
        feat = row.get('feature')
        payload = {
            'value': row.get('value'),
            'raw_value': row.get('raw_value'),
            'computed_at': str(row.get('computed_at'))
        }
        if pricing_id:
            key = f'features:{feat}:pricing:{pricing_id}'
            r.set(key, json.dumps(payload))
            written += 1
        if node_id:
            key = f'features:{feat}:node:{node_id}'
            r.set(key, json.dumps(payload))
            written += 1
    return written


def push_to_online(rows: List[Dict], feature_view_name: str = 'pricing_features') -> int:
    """Attempt to push feature rows to Feast online store; fall back to Redis.

    rows: list of dicts with keys: feature, pricing_data_id, node_id, value, raw_value, computed_at
    Returns number of feature points written (approx).
    """
    try:
        # attempt to use Feast feature store push APIs
        from feast import FeatureStore
        import pandas as pd
        from pathlib import Path

        repo_path = Path(__file__).resolve().parents[1]
        fs = FeatureStore(repo_path=str(repo_path))

        # Build a DataFrame shaped for a push: each row represents an entity with feature columns.
        # We'll pivot rows by pricing_data_id and feature name.
        df_rows = {}
        for r in rows:
            pid = r.get('pricing_data_id') or r.get('node_id')
            if pid is None:
                continue
            key = pid
            if key not in df_rows:
                df_rows[key] = {'pricing_data_id': int(r.get('pricing_data_id')) if r.get('pricing_data_id') else None, 'node_id': r.get('node_id')}
            df_rows[key][r['feature']] = r.get('value')
            # event_timestamp could be provided; Feast expects an event timestamp column named 'event_timestamp'
            df_rows[key].setdefault('event_timestamp', r.get('computed_at'))

        if not df_rows:
            return 0

        import pandas as pd
        df = pd.DataFrame(list(df_rows.values()))

        # Try to push into online store using available APIs. Different Feast versions expose different functions.
        try:
            # Newer Feast has `write_to_online_store` or `push` on FeatureStore
            if hasattr(fs, 'write_to_online_store'):
                fs.write_to_online_store(df, feature_view=feature_view_name)
                return len(df)
            elif hasattr(fs, 'push'):
                fs.push(df, feature_view_name)
                return len(df)
            else:
                # unsupported Feast version; fall back
                logger.debug('Feast does not support write_to_online_store/push on this version')
                return _write_to_redis(rows)
        except Exception:
            logger.exception('Feast push failed; falling back to Redis')
            return _write_to_redis(rows)

    except Exception:
        logger.debug('Feast not available; using Redis fallback')
        return _write_to_redis(rows)


def register_features(feature_view_name: str = 'pricing_features') -> bool:
    """Register basic entity and FeatureView with Feast using a PushSource.

    This is best-effort: if Feast is not installed or API differs, this will
    return False and log the problem. It is safe to call repeatedly.
    """
    try:
        from feast import FeatureStore, Entity, FeatureView, Feature, PushSource, ValueType
        from pathlib import Path

        repo_path = Path(__file__).resolve().parents[1]
        fs = FeatureStore(repo_path=str(repo_path))

        # Define entity
        entity = Entity(name='pricing_data', join_keys=['pricing_data_id'])

        # Define features
        features = [
            Feature(name='current_price', dtype=ValueType.DOUBLE),
            Feature(name='price_history_count', dtype=ValueType.DOUBLE),
            Feature(name='latest_change_pct', dtype=ValueType.DOUBLE),
        ]

        # PushSource for streaming/push ingestion
        push_source = PushSource(name=f'{feature_view_name}_push_source')

        fv = FeatureView(
            name=feature_view_name,
            entities=['pricing_data'],
            ttl=None,
            features=features,
            online=True,
            source=push_source,
        )

        fs.apply([entity, push_source, fv])
        logger.info('Registered Feast feature view %s', feature_view_name)
        return True
    except Exception:
        logger.exception('Failed to register Feast features; skipping')
        return False
