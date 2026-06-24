import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_robots_txt():
    """
    Verify that the /robots.txt endpoint returns 200 OK and an empty plain text body.
    """
    client = TestClient(app)
    response = client.get("/robots.txt")
    
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text == ""
