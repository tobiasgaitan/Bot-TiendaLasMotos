import pytest

def test_robots_txt(real_lifespan_client):
    """
    Verify that the /robots.txt endpoint returns 200 OK and an empty plain text body.

    [Incidente H-A · HA-2] El cliente atraviesa el LIFESPAN REAL de producción
    (fixture real_lifespan_client) — catálogo dinámico + guard estricto activos.
    """
    client, _items = real_lifespan_client
    response = client.get("/robots.txt")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text == ""
