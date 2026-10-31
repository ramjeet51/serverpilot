async def test_liveness(client):
    response = await client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ok"


async def test_platform_health_reports_database_and_redis(client):
    response = await client.get("/api/v1/health")
    body = response.json()["data"]
    assert body["components"]["postgres"]["status"] == "ok"
    assert body["components"]["redis"]["status"] == "ok"
    assert body["status"] in {"ok", "degraded"}
