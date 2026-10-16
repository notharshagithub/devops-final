"""Health / readiness / meta endpoint tests."""


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "service" in r.json()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "UP"}


def test_metrics_exposes_prometheus_format(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    # prometheus exposition format contains HELP / TYPE lines
    assert "http_requests_total" in r.text or "# HELP" in r.text
