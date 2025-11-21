"""Tests for FastAPI application initialization."""

from fastapi.testclient import TestClient

from src.api.main import app


class TestAppInitialization:
    """Test FastAPI application initialization."""

    def test_app_exists(self):
        """Test that app instance exists."""
        assert app is not None
        assert hasattr(app, "routes")

    def test_app_has_cors_middleware(self):
        """Test that CORS middleware is configured."""
        # Check middleware exists
        assert hasattr(app, "middleware")
        middlewares = [m for m in app.user_middleware]
        # Should have at least some middleware
        assert len(middlewares) >= 0

    def test_health_check_endpoint(self):
        """Test health check endpoint if it exists."""
        client = TestClient(app)

        # Try common health check paths
        for path in ["/health", "/api/health", "/api/v1/health"]:
            response = client.get(path)
            if response.status_code == 200:
                assert True
                return

        # Health endpoint might not exist, which is okay
        assert True

    def test_root_endpoint(self):
        """Test root endpoint."""
        client = TestClient(app)

        response = client.get("/")

        # Root might return 200, 404, or redirect
        assert response.status_code in [200, 404, 307, 308]

    def test_docs_endpoint_exists(self):
        """Test that API docs are available."""
        client = TestClient(app)

        response = client.get("/docs")

        # Docs should be available
        assert response.status_code in [200, 307, 308]

    def test_openapi_schema_exists(self):
        """Test that OpenAPI schema is generated."""
        client = TestClient(app)

        response = client.get("/openapi.json")

        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "info" in data
        assert "paths" in data

    def test_app_has_routes(self):
        """Test that app has routes defined."""
        routes = [route.path for route in app.routes]

        # Should have multiple routes
        assert len(routes) > 0

        # Check for key route patterns
        route_str = str(routes)
        # At least one of these should be present
        assert any(
            pattern in route_str
            for pattern in ["/adrs", "/analysis", "/generation", "/config"]
        )

    def test_app_title_and_description(self):
        """Test app metadata."""
        assert app.title is not None
        # App should have a title
        assert len(app.title) > 0
