import pytest

from app.core.database import get_async_sessionmaker
from app.schemas.agents import AgentReport
from app.services.agent_link import record_heartbeat, register_agent
from tests.conftest import login


async def test_server_registration_and_heartbeat(client):
    await login(client)
    created = await client.post("/api/v1/servers", json={
        "name": "k8s-worker",
        "hostname": "k8s-worker",
        "ip_address": "172.16.17.59",
        "description": "Ubuntu agent",
    })
    assert created.status_code == 201, created.text
    token = created.json()["data"]["registration_token"]
    assert token.startswith("spagent_")
    assert "registration_token" not in (await client.get("/api/v1/servers")).text

    report = AgentReport(hostname="k8s-worker", cpu_percent=5, memory_percent=10, disk_percent=20, cpu_cores=4)
    async with get_async_sessionmaker()() as db:
        registered = await register_agent(db, token, report, "127.0.0.1")
        await record_heartbeat(db, registered["agent_token"], report.model_copy(update={"cpu_percent": 6}))

    listed = (await client.get("/api/v1/servers")).json()["data"]
    assert listed[0]["status"] == "online"
    assert listed[0]["cpu_percent"] == 6
    assert listed[0]["os_name"] is None or isinstance(listed[0]["os_name"], str)

    with pytest.raises(PermissionError):
        async with get_async_sessionmaker()() as db:
            await register_agent(db, token, report, "127.0.0.1")
