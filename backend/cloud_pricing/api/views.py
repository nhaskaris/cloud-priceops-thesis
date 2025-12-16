import logging
import os 
import mimetypes
from wsgiref.util import FileWrapper 

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from celery.result import AsyncResult
from django.http import StreamingHttpResponse
from django.core.files.storage import default_storage
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes

from ..models import NormalizedPricingData
from .serializers import PricingDataSerializer
from ..tasks import export_pricing_data_to_csv
from django.http import HttpResponse

logger = logging.getLogger(__name__)

class NormalizedPricingDataViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NormalizedPricingData.objects.all()
    serializer_class = PricingDataSerializer
    permission_classes = [AllowAny]
    
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['domain_label']
    
    def get_queryset(self):
        # Mandatory base filters that apply to ALL list queries
        queryset = NormalizedPricingData.objects.filter(is_active=True, effective_price_per_hour__gt=0)
        return queryset
    
    # ----------------------------------------------------------------------
    # ACTION 1: START EXPORT TASK (POST /export/)
    # ----------------------------------------------------------------------
    @extend_schema(
        summary="Start CSV Export Task",
        description="Queues a Celery task to generate a filtered CSV file for training/testing data.",
        parameters=[
            OpenApiParameter(
                name='domain_label',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='OPTIONAL: Filters the data used for export.',
                required=False,
            ),
        ],
        responses={
            202: {'description': 'Task queued', 'content': {'application/json': {'example': {'task_id': 'uuid', 'status': 'Task queued. Check status endpoint for file.'}}}},
        }
    )
    @action(detail=False, methods=['post'], url_path='export')
    def export_start(self, request):
        # Get the current queryset filters (e.g., domain_label)
        # Note: dict() converts the QueryDict to a standard Python dictionary of lists
        filters = dict(request.query_params) 
        
        task = export_pricing_data_to_csv.delay(filters=filters)
        
        return Response(
            {'task_id': task.id, 'status': 'Task queued. Check status endpoint for file.'}, 
            status=status.HTTP_202_ACCEPTED
        )

    # ----------------------------------------------------------------------
    # ACTION 2: CHECK STATUS / DOWNLOAD FILE (GET /export-status/)
    # ----------------------------------------------------------------------
    @extend_schema(
        summary="Check Export Status and Download File",
        description="Poll this endpoint using the task_id. Once successful, use ?download=true to retrieve the file.",
        parameters=[
            OpenApiParameter(
                name='task_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description='MANDATORY: The unique ID returned by the /export/ endpoint.',
                required=True,
            ),
            OpenApiParameter(
                name='download',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='OPTIONAL: If true, and the task is successful, returns the file content (attachment). If false, returns status JSON.',
                required=False,
            ),
        ],
    )
    @action(detail=False, methods=['get'], url_path='export-status')
    def export_status(self, request):
        task_id = request.query_params.get('task_id') 

        if not task_id:
            return Response({"error": "task_id query parameter is required."}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        result = AsyncResult(task_id)
        
        if result.ready():
            if result.successful():
                file_info = result.result
                file_name = file_info['file_name']
                file_size = file_info.get('file_size')
                
                if not default_storage.exists(file_name):
                    logger.error(f"Export file {file_name} not found for task {task_id}.")
                    return Response({'status': 'FAILURE', 'error': 'Export file not found in storage.'}, 
                                    status=status.HTTP_404_NOT_FOUND)

                if request.query_params.get('download', 'false').lower() == 'true':
                    
                    # --- START OF X-ACCEL-REDIRECT IMPLEMENTATION ---
                    try:
                        # 1. Prepare Response
                        # Create an empty response; Nginx will fill it with file data.
                        response = HttpResponse()
                        
                        # 2. Set X-Accel-Redirect Header
                        # This tells Nginx to look in its configured location (/exports/)
                        # and serve the file specified by file_name (which is relative to /app/media/).
                        redirect_path = f"/exports/{file_name}" 
                        response['X-Accel-Redirect'] = redirect_path
                        
                        # 3. Set Standard Download Headers for the Client
                        content_type = mimetypes.guess_type(file_name)[0] or 'text/csv'
                        response['Content-Type'] = content_type
                        response['Content-Disposition'] = f'attachment; filename="{file_name}"'
                        
                        # Add content length to help the client track download progress
                        if file_size:
                            response['Content-Length'] = file_size

                        # 4. Cleanup (RISK ALERT: Delete immediately after setting redirect)
                        # Note: We delete the file immediately here because Django cannot know 
                        # when Nginx is done streaming it. For robust cleanup, use a cron job.
                        # default_storage.delete(file_name)
                        logger.info(f"Successfully initiated deletion signal for exported file: {file_name}")

                        # Nginx takes over and streams the 300MB file directly.
                        return response
                            
                    except Exception as e:
                        logger.error(f"CRITICAL REDIRECT ERROR (Task {task_id}): {e}", exc_info=True)
                        return Response({'status': 'FAILURE', 'error': f'Failed to initiate file download: {e}'}, 
                                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                    # --- END OF X-ACCEL-REDIRECT IMPLEMENTATION ---
                
                return Response({'status': 'SUCCESS', 'file_info': file_info, 'task_id': task_id}, status=status.HTTP_200_OK)
            
            else:
                task_exception = result.result
                logger.error(f"Celery task {task_id} failed. Exception: {task_exception}", exc_info=True)
                error_message = str(task_exception) if task_exception else "Unknown task failure."
                return Response({
                    'status': 'FAILURE', 
                    'error': 'Export failed on the server. Check logs for detail.', 
                    'celery_error': error_message
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'status': result.state, 'task_id': task_id}, status=status.HTTP_200_OK)