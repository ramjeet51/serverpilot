from tests.conftest import login


async def test_diagnostics_job_persists_and_completes(client):
    await login(client)
    created = await client.post("/api/v1/jobs", json={"job_type": "platform.diagnostics", "params": {}})
    assert created.status_code == 201, created.text
    job = created.json()["data"]
    assert job["status"] == "succeeded"
    assert job["result"]["healthy"] is True

    fetched = await client.get(f"/api/v1/jobs/{job['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["data"]["status"] == "succeeded"

    logs = await client.get(f"/api/v1/jobs/{job['id']}/logs")
    messages = [entry["message"] for entry in logs.json()["data"]]
    assert any("PostgreSQL" in message for message in messages)


async def test_unknown_job_type_is_rejected(client):
    await login(client)
    response = await client.post("/api/v1/jobs", json={"job_type": "shell.exec", "params": {"command": "id"}})
    assert response.status_code == 422


async def test_failed_job_can_be_retried(client):
    await login(client)
    created = await client.post("/api/v1/jobs", json={
        "job_type": "platform.sleep_test",
        "params": {"duration_seconds": 1, "fail_at_end": True},
    })
    job = created.json()["data"]
    assert job["status"] == "failed"
    retried = await client.post(f"/api/v1/jobs/{job['id']}/retry")
    assert retried.status_code == 200
    assert retried.json()["data"]["status"] == "failed"
    assert retried.json()["data"]["attempts"] == 2


async def test_stats(client):
    await login(client)
    await client.post("/api/v1/jobs", json={"job_type": "platform.diagnostics", "params": {}})
    stats = await client.get("/api/v1/jobs/stats")
    assert stats.status_code == 200
    assert stats.json()["data"]["succeeded"] >= 1
