from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_security_headers_present():
    # Make a request to a non-existent route to ensure middleware runs regardless of status code
    response = client.get("/this_route_does_not_exist_12345")

    # Check headers are present in the response
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"
    assert response.headers.get("Strict-Transport-Security") == "max-age=31536000; includeSubDomains"
