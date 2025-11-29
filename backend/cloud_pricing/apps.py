from django.apps import AppConfig
import logging
import os
import sys

logger = logging.getLogger(__name__)


class CloudPricingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cloud_pricing'