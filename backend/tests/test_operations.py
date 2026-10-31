import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from app.services.catalogue import CATALOGUE, normalize_unit
from tests.conftest import login

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "agent" / "modules" / "helper_ops.py"


def _helper(payload: dict) -> dict:
    process = subprocess.run([sys.executable, str(HELPER)], input=json.dumps(payload), text=True,
                             capture_output=True, timeout=20)
    return json.loads(process.stdout)


def _agent_catalogue():
    spec = importlib.util.spec_from_file_location("agent_catalogue", ROOT / "agent" / "modules" / "catalogue.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.CATALOGUE


def test_catalogue_matches_agent_allowlist():
    agent = _agent_catalogue()
    assert set(CATALOGUE) == set(agent)
    assert "nginx" in CATALOGUE
    assert "git" in CATALOGUE
    assert "java" in CATALOGUE
    assert len(CATALOGUE) == 22
    assert CATALOGUE["jenkins"].requires == ("java",)
    assert CATALOGUE["docker-compose"].requires == ("docker-engine",)
    for software_id, spec in CATALOGUE.items():
        assert tuple(agent[software_id].get("requires", ())) == spec.requires
        for req_id in spec.requires:
            assert req_id in CATALOGUE and req_id != software_id


def test_archive_names_reject_protected_and_injected_packages():
    from app.services.catalogue import validate_archive_package
    assert validate_archive_package("htop") == "htop"
    for bad in ("bash", "linux-image-generic", "nginx;id", "../git", "-rf"):
        try:
            validate_archive_package(bad)
        except ValueError:
            continue
        raise AssertionError(bad)


def test_helper_rejects_archive_install_of_protected_packages():
    assert _helper({"op": "software.archive", "package": "bash"})["error"] == "protected_package"
    assert _helper({"op": "software.archive", "package": "nginx;id"})["error"] == "invalid_request"


def test_unit_names_are_constrained():
    assert normalize_unit("nginx") == "nginx.service"
    for bad in ("../sshd", "ssh;id", "/lib/systemd/system/ssh.service", "-rf"):
        try:
            normalize_unit(bad)
        except ValueError:
            continue
        raise AssertionError(bad)


def test_helper_rejects_unlisted_and_protected_operations():
    protected = _helper({"op": "software.apply", "action": "remove", "software_id": "python"})
    assert protected["error"] == "protected_package"
    unknown = _helper({"op": "software.apply", "action": "install", "software_id": "cowsay"})
    assert unknown["error"] == "invalid_request"
    shell = _helper({"op": "shell", "command": "id"})
    assert shell["error"] == "invalid_request"
    ssh = _helper({"op": "services.apply", "action": "stop", "unit": "ssh"})
    assert ssh["error"] == "invalid_request"
    disabled = _helper({"op": "services.apply", "action": "disable", "unit": "ssh"})
    assert disabled["error"] == "protected_service"
    traversal = _helper({"op": "services.apply", "action": "restart", "unit": "../../tmp/evil"})
    assert traversal["error"] == "invalid_unit"


async def test_software_api_guards_and_offline_job(client):
    await login(client)
    catalogue = await client.get("/api/v1/software/catalogue")
    assert catalogue.status_code == 200
    assert any(item["id"] == "nginx" for item in catalogue.json()["data"])

    created = await client.post("/api/v1/servers", json={
        "name": "pkg-host", "hostname": "pkg-host", "ip_address": "172.16.17.59", "description": "operations test",
    })
    server_id = created.json()["data"]["server"]["id"]

    listed = await client.get("/api/v1/software", params={"server_id": server_id})
    assert listed.status_code == 200
    nginx = next(item for item in listed.json()["data"] if item["id"] == "nginx")
    assert nginx["status"] == "unknown"

    removed = await client.post("/api/v1/software/operations", json={
        "server_id": server_id, "software_id": "python", "action": "remove", "confirm": True,
    })
    assert removed.status_code == 400
    assert removed.json()["error"]["code"] == "protected_package"

    unconfirmed = await client.post("/api/v1/software/operations", json={
        "server_id": server_id, "software_id": "nginx", "action": "remove", "confirm": False,
    })
    assert unconfirmed.status_code == 400

    stopped = await client.post("/api/v1/services/operations", json={
        "server_id": server_id, "unit": "ssh", "action": "stop", "confirm": True,
    })
    assert stopped.status_code == 422
    disabled = await client.post("/api/v1/services/operations", json={
        "server_id": server_id, "unit": "ssh", "action": "disable", "confirm": True,
    })
    assert disabled.status_code == 400
    assert disabled.json()["error"]["code"] == "protected_service"

    install = await client.post("/api/v1/software/operations", json={
        "server_id": server_id, "software_id": "nginx", "action": "install", "confirm": True,
    })
    assert install.status_code == 201, install.text
    job = install.json()["data"]
    assert job["status"] == "failed"
    assert "not connected" in job["error_message"].lower()

    audit = await client.get("/api/v1/audit")
    actions = {entry["action"] for entry in audit.json()["data"]}
    assert "software.install" in actions
    assert "software.apply.failure" in actions
