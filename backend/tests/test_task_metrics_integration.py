"""Integration test for task metrics endpoint."""


from fastapi.testclient import TestClient

from backend.app.main import AppConfig, create_app


def test_task_metrics_endpoint_integration():
    """Integration test: verify /api/metrics/tasks endpoint is accessible and returns valid data."""
    test_config = AppConfig(enable_binance_stream=False)
    app = create_app(test_config)
    with TestClient(app) as client:
        # Make request to the metrics endpoint
        response = client.get("/api/metrics/tasks")

        # Verify successful response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        # Parse response
        data = response.json()

        # Verify response structure matches TaskMetrics
        expected_fields = {
            "current_task_count",
            "queue_depth",
            "rejected_count",
            "completed_count",
            "failed_count",
        }
        assert set(data.keys()) == expected_fields, f"Missing or extra fields in response: {data.keys()}"

        # Verify all values are non-negative integers
        for field, value in data.items():
            assert isinstance(value, int), f"{field} should be int, got {type(value)}"
            assert value >= 0, f"{field} should be non-negative, got {value}"

        print(f"✓ Task metrics endpoint working correctly: {data}")


def test_task_metrics_endpoint_path():
    """Verify the endpoint is accessible at the correct path."""
    test_config = AppConfig(enable_binance_stream=False)
    app = create_app(test_config)
    with TestClient(app) as client:
        # Test the full path
        response = client.get("/api/metrics/tasks")
        assert response.status_code == 200

        # Verify it's not accessible without the /api prefix
        response_without_prefix = client.get("/metrics/tasks")
        assert response_without_prefix.status_code == 404
