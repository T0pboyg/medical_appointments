import os

import httpx


async def get_access_checker_token():
    token_url = (
        "http://keycloak:8080/realms/"
        "medical-appointments/protocol/openid-connect/token"
    )

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": os.environ["KEYCLOAK_ACCESS_CLIENT_ID"],
                "client_secret": os.environ["KEYCLOAK_ACCESS_CLIENT_SECRET"],
            },
        )

        response.raise_for_status()
        return response.json()["access_token"]

async def is_active_staff(subject):
    token = await get_access_checker_token()

    user_url = (
        "http://keycloak:8080/admin/realms/"
        f"medical-appointments/users/{subject}"
    )

    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(
        timeout=5.0,
        headers=headers,
    ) as client:
        user_response = await client.get(user_url)

        if user_response.status_code == 404:
            return False

        user_response.raise_for_status()

        if user_response.json().get("enabled") is not True:
            return False

        roles_response = await client.get(
            f"{user_url}/role-mappings/realm/composite"
        )
        roles_response.raise_for_status()

        roles = roles_response.json()
        return any(role.get("name") == "staff" for role in roles)