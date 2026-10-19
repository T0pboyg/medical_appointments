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

        try:
            token_data = response.json()
        except ValueError:
            raise httpx.RequestError(
                "Invalid Keycloak token response.",
                request=response.request,
            ) from None

        if not isinstance(token_data, dict):
            raise httpx.RequestError(
                "Invalid Keycloak token response structure.",
                request=response.request,
            )

        token = token_data.get("access_token")

        if not isinstance(token, str) or not token.strip():
            raise httpx.RequestError(
                "Missing or invalid Keycloak access token.",
                request=response.request,
            )

        return token

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

        try:
            user_data = user_response.json()
        except ValueError:
            raise httpx.RequestError(
                "Invalid Keycloak user response.",
                request=user_response.request,
            ) from None

        if not isinstance(user_data, dict):
            raise httpx.RequestError(
                "Invalid Keycloak user response structure.",
                request=user_response.request,
            )

        if user_data.get("enabled") is not True:
            return False

        roles_response = await client.get(
            f"{user_url}/role-mappings/realm/composite"
        )
        roles_response.raise_for_status()

        try:
            roles = roles_response.json()
        except ValueError:
            raise httpx.RequestError(
                "Invalid Keycloak roles response.",
                request=roles_response.request,
            ) from None

        if not isinstance(roles, list) or not all(
            isinstance(role, dict)
            and isinstance(role.get("name"), str)
            for role in roles
        ):
            raise httpx.RequestError(
                "Invalid Keycloak roles response structure.",
                request=roles_response.request,
            )

        return any(role["name"] == "staff" for role in roles)