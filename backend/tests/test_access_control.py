import unittest
from unittest.mock import AsyncMock, patch

import httpx

from access_control import is_active_staff
from access_control import get_access_checker_token, is_active_staff


class AccessControlTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_user_json_is_service_error(self):
        response = httpx.Response(
            200,
            content=b"invalid-json",
            request=httpx.Request(
                "GET",
                "http://keycloak:8080/admin/realms/"
                "medical-appointments/users/test-subject",
            ),
        )

        with (
            patch(
                "access_control.get_access_checker_token",
                new_callable=AsyncMock,
                return_value="test-token",
            ),
            patch(
                "access_control.httpx.AsyncClient",
            ) as client_class,
        ):
            client = client_class.return_value.__aenter__.return_value
            client.get = AsyncMock(return_value=response)

            with self.assertRaises(httpx.HTTPError):
                await is_active_staff("test-subject")

    async def test_invalid_user_structure_is_service_error(self):
        response = httpx.Response(
            200,
            json=[],
            request=httpx.Request(
                "GET",
                "http://keycloak:8080/admin/realms/"
                "medical-appointments/users/test-subject",
            ),
        )

        with (
            patch(
                "access_control.get_access_checker_token",
                new_callable=AsyncMock,
                return_value="test-token",
            ),
            patch(
                "access_control.httpx.AsyncClient",
            ) as client_class,
        ):
            client = client_class.return_value.__aenter__.return_value
            client.get = AsyncMock(return_value=response)

            with self.assertRaises(httpx.HTTPError):
                await is_active_staff("test-subject")

    async def test_invalid_roles_structure_is_service_error(self):
        user_url = (
            "http://keycloak:8080/admin/realms/"
            "medical-appointments/users/test-subject"
        )

        user_response = httpx.Response(
            200,
            json={"enabled": True},
            request=httpx.Request("GET", user_url),
        )
        roles_response = httpx.Response(
            200,
            json={"unexpected": "structure"},
            request=httpx.Request(
                "GET",
                f"{user_url}/role-mappings/realm/composite",
            ),
        )

        with (
            patch(
                "access_control.get_access_checker_token",
                new_callable=AsyncMock,
                return_value="test-token",
            ),
            patch("access_control.httpx.AsyncClient") as client_class,
        ):
            client = client_class.return_value.__aenter__.return_value
            client.get = AsyncMock(
                side_effect=[user_response, roles_response],
            )

            with self.assertRaises(httpx.HTTPError):
                await is_active_staff("test-subject")


    async def test_missing_access_token_is_service_error(self):
        response = httpx.Response(
            200,
            json={},
            request=httpx.Request(
                "POST",
                "http://keycloak:8080/realms/"
                "medical-appointments/protocol/openid-connect/token",
            ),
        )

        with patch("access_control.httpx.AsyncClient") as client_class:
            client = client_class.return_value.__aenter__.return_value
            client.post = AsyncMock(return_value=response)

            with self.assertRaises(httpx.HTTPError):
                await get_access_checker_token()

    async def test_active_staff_is_accepted(self):
        user_url = (
            "http://keycloak:8080/admin/realms/"
            "medical-appointments/users/test-subject"
        )

        responses = [
            httpx.Response(
                200,
                json={"enabled": True},
                request=httpx.Request("GET", user_url),
            ),
            httpx.Response(
                200,
                json=[{"name": "staff"}],
                request=httpx.Request(
                    "GET",
                    f"{user_url}/role-mappings/realm/composite",
                ),
            ),
        ]

        with (
            patch(
                "access_control.get_access_checker_token",
                new_callable=AsyncMock,
                return_value="test-token",
            ),
            patch("access_control.httpx.AsyncClient") as client_class,
        ):
            client = client_class.return_value.__aenter__.return_value
            client.get = AsyncMock(side_effect=responses)

            result = await is_active_staff("test-subject")

        self.assertTrue(result)


    async def test_disabled_user_is_rejected(self):
        user_url = (
            "http://keycloak:8080/admin/realms/"
            "medical-appointments/users/test-subject"
        )

        response = httpx.Response(
            200,
            json={"enabled": False},
            request=httpx.Request("GET", user_url),
        )

        with (
            patch(
                "access_control.get_access_checker_token",
                new_callable=AsyncMock,
                return_value="test-token",
            ),
            patch("access_control.httpx.AsyncClient") as client_class,
        ):
            client = client_class.return_value.__aenter__.return_value
            client.get = AsyncMock(return_value=response)

            result = await is_active_staff("test-subject")

            self.assertFalse(result)
            client.get.assert_awaited_once_with(user_url)

    async def test_user_without_staff_role_is_rejected(self):
        user_url = (
            "http://keycloak:8080/admin/realms/"
            "medical-appointments/users/test-subject"
        )

        responses = [
            httpx.Response(
                200,
                json={"enabled": True},
                request=httpx.Request("GET", user_url),
            ),
            httpx.Response(
                200,
                json=[{"name": "visitor"}],
                request=httpx.Request(
                    "GET",
                    f"{user_url}/role-mappings/realm/composite",
                ),
            ),
        ]

        with (
            patch(
                "access_control.get_access_checker_token",
                new_callable=AsyncMock,
                return_value="test-token",
            ),
            patch("access_control.httpx.AsyncClient") as client_class,
        ):
            client = client_class.return_value.__aenter__.return_value
            client.get = AsyncMock(side_effect=responses)

            result = await is_active_staff("test-subject")

        self.assertFalse(result)