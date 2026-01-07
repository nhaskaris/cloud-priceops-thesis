"""
Load Testing Suite for Cloud PriceOps - Locust Configuration

This test suite validates the framework's operational stability under concurrent load,
specifically testing the "Bottleneck" scenario: simultaneous API queries during 
heavy background data ingestion.

Section 5.4.2: Integration and Stress Testing of the Service Mesh
"""

from locust import HttpUser, task, between
import random
import logging

logger = logging.getLogger(__name__)


class PricingPredictionUser(HttpUser):
    """
    Simulates a user making price prediction requests.
    
    This task represents the "Financial Planner" scenario:
    - Rapidly queries the matching score algorithm
    - Tests vCPU, memory, and region combinations
    - Validates response times under load
    """
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between requests
    
    def on_start(self):
        """Initialize user session - fetch available model types"""
        # Get available model types from the API
        with self.client.get(
            "/api/engines/types/",
            catch_response=True
        ) as resp:
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    # Extract model types from response (preserve case from API)
                    if isinstance(data, list):
                        self.model_types = [item.get('type', '') for item in data if item.get('type')]
                        # Remove duplicates while preserving order
                        seen = set()
                        self.model_types = [x for x in self.model_types if not (x in seen or seen.add(x))]
                    if not self.model_types:
                        self.model_types = ["Regression", "Hedonic"]
                except:
                    self.model_types = ["Regression", "Hedonic"]
            else:
                # Fallback to defaults if endpoint fails
                self.model_types = ["Regression", "Hedonic"]
    
    @task(7)
    def predict_instance_pricing(self):
        """
        Heavy task: Request price prediction for a random instance spec.
        This simulates the Financial Planner querying for cost estimates.
        
        Expected: Response time <200ms per thesis requirement
        Note: 404 is expected if no models are trained yet
        """
        if not self.model_types:
            return  # Skip if no models available
        
        model_type = random.choice(self.model_types)
        vcpu = random.choice([1, 2, 4, 8, 16])
        memory = random.choice([4, 8, 16, 32, 64])
        region = random.choice(["us-east-1", "us-west-2", "eu-west-1"])
        
        with self.client.post(
            f"/api/engines/predict-by-type/{model_type}/",
            json={
                "vcpu_count": vcpu,
                "memory_gb": memory,
                "region": region,
                "operating_system": random.choice(["Linux", "Windows"]),
                "tenancy": random.choice(["default", "shared", "dedicated"]),
            },
            catch_response=True,
            name="/api/engines/predict-by-type/[type]/"
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 404:
                # 404 is expected if no models trained yet - don't count as failure
                resp.success()
            else:
                resp.failure(f"Status: {resp.status_code}")
    
    @task(2)
    def list_model_types(self):
        """
        Lightweight task: Fetch available model types.
        Tests that metadata endpoints remain responsive under load.
        """
        with self.client.get(
            "/api/engines/types/",
            catch_response=True
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Status: {resp.status_code}")


class DataExportUser(HttpUser):
    """
    Simulates a user exporting pricing datasets.
    
    Validates that large CSV exports (X-Accel-Redirect) don't block other operations.
    This represents the "Researcher" scenario from thesis section 5.4.3.
    """
    
    wait_time = between(5, 10)  # Less frequent (exports are slower)
    
    def on_start(self):
        """Initialize - start an export to get a task_id"""
        self.last_task_id = None
    
    @task(1)
    def request_csv_export(self):
        """
        Request CSV export of filtered pricing data.
        Heavy background task that shouldn't block API responses.
        
        Expected: Export queued quickly with 202 ACCEPTED response
        """
        domain = random.choice(["iaas", "paas", "database", "storage"])
        
        with self.client.post(
            "/api/normalized-pricing-data/export/",
            params={"domain_label": domain},
            catch_response=True,
            name="/api/normalized-pricing-data/export/"
        ) as resp:
            if resp.status_code == 202:  # 202 Accepted for async task
                # Store task_id for status checks
                try:
                    task_data = resp.json()
                    self.last_task_id = task_data.get('task_id')
                except:
                    pass
                resp.success()
            else:
                resp.failure(f"Status: {resp.status_code}")
    
    @task(3)
    def check_export_status(self):
        """
        Poll export status using task_id from previous request.
        Validates that UI can remain responsive while background tasks run.
        
        Expected: Response time <100ms
        """
        if not self.last_task_id:
            return  # Skip if no task_id available
        
        with self.client.get(
            "/api/normalized-pricing-data/export-status/",
            params={"task_id": self.last_task_id},
            catch_response=True,
            name="/api/normalized-pricing-data/export-status/"
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Status: {resp.status_code}")


class ModelManagementUser(HttpUser):
    """
    Simulates a researcher uploading and querying ML models.
    
    Validates model registry endpoints under moderate load.
    """
    
    wait_time = between(10, 20)  # Infrequent - model uploads are rare
    
    @task(2)
    def list_models(self):
        """Fetch all registered models"""
        with self.client.get(
            "/api/engines/summary/",
            catch_response=True
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Status: {resp.status_code}")
    
    @task(1)
    def get_model_types(self):
        """Fetch available model types and best performers"""
        with self.client.get(
            "/api/engines/types/",
            catch_response=True
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Status: {resp.status_code}")


if __name__ == "__main__":
    """
    Usage:
        locust -f locustfile.py -u 50 -r 10 -t 5m --host=http://localhost
    
    Arguments:
        -u 50          : 50 concurrent virtual users
        -r 10          : Ramp up 10 users per second
        -t 5m          : Run for 5 minutes
        --host         : Target URL (http://localhost or http://your-server)
    
    Expected Results (from thesis 5.4.2):
        - Response time <200ms for prediction endpoints during concurrent load
        - Nginx buffering prevents UI freeze during heavy background ingestion
        - Throughput: >100 requests/sec at p99 latency <500ms
    """
    pass
