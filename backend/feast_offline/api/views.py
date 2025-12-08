from datetime import datetime, timezone
import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from feast import FeatureStore
import pandas as pd

from .serializers import (
    FeatureRequestSerializer,
    FeatureResponseSerializer,
    OnlineFeatureBatchResponseSerializer,
    TrainingDataBatchResponseSerializer,
)

logger = logging.getLogger(__name__)


class GetOnlineFeaturesAPIView(APIView):
    """
    API endpoint for fetching latest features from Feast online store (Redis).
    
    POST /api/feast/features/online/
    """

    def get_feature_store(self):
        """Initialize and return Feast FeatureStore instance."""
        try:
            fs = FeatureStore(repo_path="feast_offline/feature_repo")
            return fs
        except Exception as e:
            logger.error(f"Failed to initialize FeatureStore: {str(e)}")
            raise

    def get(self, request):
        """
        Fetch latest features from online store (Redis).
        
        GET /api/feast/features/online/
        GET /api/feast/features/online/?pricing_data_ids=1,2,3
        GET /api/feast/features/online/?pricing_data_ids=1,2,3&columns=current_price,previous_price
        
        Query parameters:
        - pricing_data_ids (optional): comma-separated list of IDs (e.g., 1,2,3). If not provided, fetches all available features.
        - columns (optional): comma-separated list of columns to return. If not provided, returns all columns.
          Available columns: current_price, previous_price, price_diff_abs, price_diff_pct, days_since_price_change, price_change_frequency_90d
        
        Response:
        {
            "status": "success",
            "count": 3,
            "features": [
                {
                    "pricing_data_id": 1,
                    "current_price": 10.5,
                    "previous_price": 9.8
                }
            ]
        }
        """
        # Parse query parameters
        pricing_data_ids_str = request.query_params.get('pricing_data_ids', '')
        columns_str = request.query_params.get('columns', '')
        
        # Parse pricing_data_ids if provided, otherwise leave empty to fetch all
        if pricing_data_ids_str:
            try:
                pricing_data_ids = [int(x.strip()) for x in pricing_data_ids_str.split(',') if x.strip()]
            except ValueError:
                return Response(
                    {
                        "status": "error",
                        "message": "pricing_data_ids must be comma-separated integers",
                        "errors": ["Invalid pricing_data_ids format"]
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            pricing_data_ids = None
        
        # Parse columns parameter
        columns = [x.strip() for x in columns_str.split(',') if x.strip()] if columns_str else None

        # All available columns
        all_columns = [
            "current_price",
            "previous_price",
            "price_diff_abs",
            "price_diff_pct",
            "days_since_price_change",
            "price_change_frequency_90d"
        ]
        
        # Use specified columns or all if not provided
        columns_to_fetch = columns if columns else all_columns

        try:
            fs = self.get_feature_store()

            # If pricing_data_ids provided, fetch only those; otherwise fetch all from Redis
            if pricing_data_ids:
                # Get online features from Redis for specific IDs
                features_df = fs.get_online_features(
                    features=[f"pricing_data_features:{col}" for col in columns_to_fetch],
                    entity_rows=[
                        {"pricing_data_id": pid} for pid in pricing_data_ids
                    ]
                )
            else:
                # No IDs provided - fetch all available data from the online store
                # This requires querying the offline store first to get all IDs
                from django.db import connection as django_connection
                
                try:
                    with django_connection.cursor() as cursor:
                        cursor.execute("SELECT DISTINCT pricing_data_id FROM pricing_features ORDER BY pricing_data_id")
                        all_ids = [row[0] for row in cursor.fetchall()]
                    
                    if not all_ids:
                        features_df = None
                    else:
                        # Get online features from Redis for all IDs
                        features_df = fs.get_online_features(
                            features=[f"pricing_data_features:{col}" for col in columns_to_fetch],
                            entity_rows=[
                                {"pricing_data_id": pid} for pid in all_ids
                            ]
                        )
                except Exception as db_error:
                    logger.error(f"Error fetching all pricing_data_ids: {str(db_error)}")
                    features_df = None

            # Convert to list of dicts with only requested columns
            features_list = []
            if features_df is not None:
                for idx, row in features_df.iterrows():
                    feature_dict = {"pricing_data_id": row.get("pricing_data_id")}
                    
                    # Add only requested columns
                    for col in columns_to_fetch:
                        value = row.get(col)
                        feature_dict[col] = value
                    
                    features_list.append(feature_dict)

            response_data = {
                "status": "success",
                "count": len(features_list),
                "features": features_list
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error fetching online features: {str(e)}")
            return Response(
                {
                    "status": "error",
                    "message": str(e),
                    "count": 0,
                    "features": [],
                    "errors": [str(e)]
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GetTrainingDataAPIView(APIView):
    """
    API endpoint for fetching training data from Feast offline store (PostgreSQL).
    
    POST /api/feast/features/training-data/
    """

    def get_feature_store(self):
        """Initialize and return Feast FeatureStore instance."""
        try:
            fs = FeatureStore(repo_path="feast_offline/feature_repo")
            return fs
        except Exception as e:
            logger.error(f"Failed to initialize FeatureStore: {str(e)}")
            raise

    def get(self, request):
        """
        Fetch training data (historical features) from offline store (PostgreSQL).
        
        GET /api/feast/features/training-data/
        GET /api/feast/features/training-data/?pricing_data_ids=1,2,3
        GET /api/feast/features/training-data/?pricing_data_ids=1,2,3&columns=current_price,previous_price&timestamp=2024-12-01T00:00:00Z
        
        Query parameters:
        - pricing_data_ids (optional): comma-separated list of IDs (e.g., 1,2,3). If not provided, returns empty list.
        - columns (optional): comma-separated list of columns. If not provided, returns all columns.
          Available columns: current_price, previous_price, price_diff_abs, price_diff_pct, days_since_price_change, price_change_frequency_90d
        - timestamp (optional): ISO format timestamp for historical features (defaults to now)
        
        Response:
        {
            "status": "success",
            "count": 3,
            "training_data": [
                {
                    "pricing_data_id": 1,
                    "current_price": 10.5,
                    "previous_price": 9.8,
                    "event_timestamp": "2024-12-01T00:00:00Z"
                }
            ]
        }
        """
        # Parse query parameters
        pricing_data_ids_str = request.query_params.get('pricing_data_ids', '')
        columns_str = request.query_params.get('columns', '')
        timestamp_str = request.query_params.get('timestamp')
        
        # Parse pricing_data_ids if provided, otherwise leave empty
        if pricing_data_ids_str:
            try:
                pricing_data_ids = [int(x.strip()) for x in pricing_data_ids_str.split(',') if x.strip()]
            except ValueError:
                return Response(
                    {
                        "status": "error",
                        "message": "pricing_data_ids must be comma-separated integers",
                        "errors": ["Invalid pricing_data_ids format"]
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            pricing_data_ids = None
        
        # Parse columns parameter
        columns = [x.strip() for x in columns_str.split(',') if x.strip()] if columns_str else None
        
        # Parse timestamp
        timestamp = None
        if timestamp_str:
            try:
                from django.utils.dateparse import parse_datetime
                timestamp = parse_datetime(timestamp_str)
                if not timestamp:
                    return Response(
                        {
                            "status": "error",
                            "message": "Invalid timestamp format. Use ISO format (e.g., 2024-12-01T00:00:00Z)",
                            "errors": ["Invalid timestamp"]
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except Exception as e:
                return Response(
                    {
                        "status": "error",
                        "message": f"Error parsing timestamp: {str(e)}",
                        "errors": ["Timestamp parse error"]
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Default to now if no timestamp provided
        if not timestamp:
            timestamp = datetime.now(timezone.utc)

        # All available columns
        all_columns = [
            "current_price",
            "previous_price",
            "price_diff_abs",
            "price_diff_pct",
            "days_since_price_change",
            "price_change_frequency_90d"
        ]
        
        # Use specified columns or all if not provided
        columns_to_fetch = columns if columns else all_columns

        try:
            fs = self.get_feature_store()

            # If pricing_data_ids provided, fetch those; otherwise fetch all
            if pricing_data_ids:
                # Build entity DataFrame for Feast with specific IDs
                entity_df = pd.DataFrame({
                    "pricing_data_id": pricing_data_ids,
                    "event_timestamp": [timestamp] * len(pricing_data_ids)
                })

                # Get historical features from PostgreSQL
                features_result = fs.get_historical_features(
                    features=[f"pricing_data_features:{col}" for col in columns_to_fetch],
                    entity_df=entity_df
                )
                
                # Convert to pandas - try different methods
                if isinstance(features_result, pd.DataFrame):
                    features_df = features_result
                elif hasattr(features_result, 'to_pandas'):
                    features_df = features_result.to_pandas()
                elif hasattr(features_result, 'to_df'):
                    features_df = features_result.to_df()
                else:
                    # Try to use list() or iterate
                    try:
                        features_df = pd.DataFrame(list(features_result))
                    except:
                        logger.error(f"Unable to convert result to DataFrame. Type: {type(features_result)}")
                        features_df = None
            else:
                # No IDs provided - fetch all available data from the offline store
                try:
                    from django.db import connection as django_connection
                    
                    with django_connection.cursor() as cursor:
                        # Try multiple possible table names
                        cursor.execute("""
                            SELECT DISTINCT pricing_data_id 
                            FROM pricing_features 
                            ORDER BY pricing_data_id
                        """)
                        all_ids = [row[0] for row in cursor.fetchall()]
                    
                    logger.info(f"Found {len(all_ids)} distinct pricing_data_ids in pricing_features table")
                    
                    if not all_ids:
                        logger.warning("No pricing_data_ids found in pricing_features table")
                        features_df = None
                    else:
                        # Build entity DataFrame for Feast with all IDs
                        entity_df = pd.DataFrame({
                            "pricing_data_id": all_ids,
                            "event_timestamp": [timestamp] * len(all_ids)
                        })

                        # Get historical features from PostgreSQL
                        features_result = fs.get_historical_features(
                            features=[f"pricing_data_features:{col}" for col in columns_to_fetch],
                            entity_df=entity_df
                        )
                        
                        # Convert to pandas - try different methods
                        if isinstance(features_result, pd.DataFrame):
                            features_df = features_result
                        elif hasattr(features_result, 'to_pandas'):
                            features_df = features_result.to_pandas()
                        elif hasattr(features_result, 'to_df'):
                            features_df = features_result.to_df()
                        else:
                            # Try to use list() or iterate
                            try:
                                features_df = pd.DataFrame(list(features_result))
                            except:
                                logger.error(f"Unable to convert result to DataFrame. Type: {type(features_result)}")
                                features_df = None
                except Exception as db_error:
                    logger.error(f"Error fetching all pricing_data_ids: {str(db_error)}")
                    features_df = None

            # Convert to list of dicts with only requested columns
            features_list = []
            if features_df is not None:
                for idx, row in features_df.iterrows():
                    feature_dict = {
                        "pricing_data_id": int(row.get("pricing_data_id")),
                        "event_timestamp": row.get("event_timestamp").isoformat() if row.get("event_timestamp") else None,
                    }
                    
                    # Add only requested columns
                    for col in columns_to_fetch:
                        value = row.get(col)
                        if value is not None:
                            feature_dict[col] = float(value)
                        else:
                            feature_dict[col] = None
                    
                    features_list.append(feature_dict)

            response_data = {
                "status": "success",
                "count": len(features_list),
                "training_data": features_list
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error fetching training data: {str(e)}")
            return Response(
                {
                    "status": "error",
                    "message": str(e),
                    "count": 0,
                    "training_data": [],
                    "errors": [str(e)]
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
