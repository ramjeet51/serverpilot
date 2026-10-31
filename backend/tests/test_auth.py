from tests.conftest import ADMIN, login


async def test_login_rejects_unknown_user(client):
    response = await client.post("/api/v1/auth/login", json={"email": "missing@serverpilot.local", "password": "whatever-1"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


async def test_login_and_profile(client):
    data = await login(client)
    assert data["user"]["email"] == ADMIN["email"]
    assert "admin" in data["user"]["roles"]
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["data"]["is_superuser"] is True


async def test_refresh_rotates_and_rejects_replay(client):
    data = await login(client)
    first = await client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": data["csrf_token"]})
    assert first.status_code == 200
    replay = await client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": data["csrf_token"]})
    assert replay.status_code == 403


async def test_refresh_requires_csrf(client):
    await login(client)
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 403


async def test_logout_revokes_session(client):
    data = await login(client)
    logged_out = await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": data["csrf_token"]})
    assert logged_out.status_code == 200
    refresh = await client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": data["csrf_token"]})
    assert refresh.status_code in (401, 403)


async def test_change_password(client):
    await login(client)
    changed = await client.post("/api/v1/auth/change-password", json={
        "current_password": ADMIN["password"],
        "new_password": "New-ServerPilot-2",
    })
    assert changed.status_code == 200
    client.headers.pop("Authorization", None)
    again = await client.post("/api/v1/auth/login", json={"email": ADMIN["email"], "password": "New-ServerPilot-2"})
    assert again.status_code == 200


async def test_viewer_cannot_create_accounts(client):
    await login(client)
    created = await client.post("/api/v1/accounts", json={
        "email": "viewer@serverpilot.local",
        "full_name": "Viewer",
        "password": "Viewer-Password-1",
        "roles": ["viewer"],
    })
    assert created.status_code == 201
    client.headers.pop("Authorization", None)
    await login(client, "viewer@serverpilot.local", "Viewer-Password-1")
    denied = await client.post("/api/v1/accounts", json={
        "email": "other@serverpilot.local",
        "full_name": "Other",
        "password": "Viewer-Password-1",
        "roles": ["viewer"],
    })
    assert denied.status_code == 403
