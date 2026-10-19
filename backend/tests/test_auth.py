import os
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import HTTPException
from starlette.requests import Request

from auth import require_staff


class StaffAccessTests(unittest.IsolatedAsyncioTestCase):
    def make_request(self):
        return Request({
            "type": "http",
            "headers": [
                (b"cookie", b"staff_session=test-session"),
            ],
        })

    def make_session(self):
        return {
            "purpose": "staff",
            "issuer": os.environ["OIDC_ISSUER"],
            "subject": "test-subject",
        }

    async def test_missing_session_is_rejected(self):
        with patch("auth.get_staff_session", return_value=None):
            with self.assertRaises(HTTPException) as error:
                await require_staff(self.make_request())

        self.assertEqual(error.exception.status_code, 401)

    async def test_removed_access_revokes_sessions(self):
        with (
            patch(
                "auth.get_staff_session",
                return_value=self.make_session(),
            ),
            patch(
                "auth.is_active_staff",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("auth.delete_staff_sessions_for_user") as revoke,
        ):
            with self.assertRaises(HTTPException) as error:
                await require_staff(self.make_request())

            self.assertEqual(error.exception.status_code, 401)
            revoke.assert_called_once_with(
                os.environ["OIDC_ISSUER"],
                "test-subject",
            )

    async def test_keycloak_outage_denies_without_revocation(self):
        with (
            patch(
                "auth.get_staff_session",
                return_value=self.make_session(),
            ),
            patch(
                "auth.is_active_staff",
                new_callable=AsyncMock,
                side_effect=httpx.ConnectError("Test outage"),
            ),
            patch("auth.delete_staff_sessions_for_user") as revoke,
        ):
            with self.assertRaises(HTTPException) as error:
                await require_staff(self.make_request())

            self.assertEqual(error.exception.status_code, 503)
            revoke.assert_not_called()

    async def test_missing_csrf_token_is_rejected(self):
        from auth import require_staff_change

        request = Request({
            "type": "http",
            "headers": [
                (b"origin", b"http://localhost:5173"),
            ],
        })
        session = {"csrf_token": "test-csrf-token"}

        with self.assertRaises(HTTPException) as error:
            await require_staff_change(request, session)

        self.assertEqual(error.exception.status_code, 403)


    async def test_wrong_csrf_token_is_rejected(self):
        from auth import require_staff_change

        request = Request({
            "type": "http",
            "headers": [
                (b"origin", b"http://localhost:5173"),
                (b"x-csrf-token", b"wrong-token"),
            ],
        })
        session = {"csrf_token": "correct-token"}

        with self.assertRaises(HTTPException) as error:
            await require_staff_change(request, session)

        self.assertEqual(error.exception.status_code, 403)

    async def test_wrong_origin_is_rejected(self):
        from auth import require_staff_change

        request = Request({
            "type": "http",
            "headers": [
                (b"origin", b"http://untrusted.example"),
                (b"x-csrf-token", b"correct-token"),
            ],
        })
        session = {"csrf_token": "correct-token"}

        with self.assertRaises(HTTPException) as error:
            await require_staff_change(request, session)

        self.assertEqual(error.exception.status_code, 403)

    async def test_valid_csrf_token_and_origin_are_accepted(self):
        from auth import require_staff_change

        request = Request({
            "type": "http",
            "headers": [
                (b"origin", b"http://localhost:5173"),
                (b"x-csrf-token", b"correct-token"),
            ],
        })
        session = {"csrf_token": "correct-token"}

        result = await require_staff_change(request, session)

        self.assertEqual(result, session)

    async def test_missing_origin_is_rejected(self):
        from auth import require_staff_change

        request = Request({
            "type": "http",
            "headers": [
                (b"x-csrf-token", b"correct-token"),
            ],
        })
        session = {"csrf_token": "correct-token"}

        with self.assertRaises(HTTPException) as error:
            await require_staff_change(request, session)

        self.assertEqual(error.exception.status_code, 403)

    async def test_active_staff_is_accepted(self):
        session = self.make_session()

        with (
            patch("auth.get_staff_session", return_value=session),
            patch(
                "auth.is_active_staff",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            result = await require_staff(self.make_request())

        self.assertEqual(result, session)

    async def test_wrong_issuer_is_rejected(self):
        session = self.make_session()
        session["issuer"] = "https://untrusted.example/realms/test"

        with (
            patch("auth.get_staff_session", return_value=session),
            patch(
                "auth.is_active_staff",
                new_callable=AsyncMock,
            ) as check_access,
        ):
            with self.assertRaises(HTTPException) as error:
                await require_staff(self.make_request())

            self.assertEqual(error.exception.status_code, 401)
            check_access.assert_not_awaited()