import unittest
from datetime import datetime
from unittest.mock import patch
from uuid import UUID

import psycopg
from fastapi.testclient import TestClient

from auth import require_staff_change
from main import app


class ReschedulingApiTests(unittest.TestCase):
    def setUp(self):
        self.previous_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[require_staff_change] = lambda: {
            "issuer": "synthetic-issuer",
            "subject": "synthetic-staff",
        }
        self.client = TestClient(app)
        self.payload = {
            "starts_at": "2030-01-07T10:30:00+02:00",
            "expected_starts_at": "2030-01-07T10:00:00+02:00",
        }

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.previous_overrides)

    def test_success_uses_staff_identity_and_returns_no_store(self):
        new_start = datetime.fromisoformat(self.payload["starts_at"])

        with patch(
            "main.reschedule_appointment_in_db",
            return_value={"id": 42, "starts_at": new_start},
        ) as move:
            response = self.client.post(
                "/appointments/42/reschedule",
                json=self.payload,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.json()["id"], 42)
        self.assertEqual(
            datetime.fromisoformat(response.json()["starts_at"]),
            new_start,
        )

        move.assert_called_once()
        args, kwargs = move.call_args
        self.assertEqual(
            args[:4],
            (
                42,
                new_start,
                "synthetic-issuer",
                "synthetic-staff",
            ),
        )
        self.assertIsInstance(args[4], UUID)
        self.assertEqual(
            kwargs,
            {
                "expected_starts_at": datetime.fromisoformat(
                    self.payload["expected_starts_at"]
                )
            },
        )

    def test_conflicts_return_409(self):
        for outcome in (
            None,
            psycopg.errors.UniqueViolation("Occupied"),
            psycopg.errors.CheckViolation("Blocked"),
        ):
            with self.subTest(outcome=type(outcome).__name__):
                with patch(
                    "main.reschedule_appointment_in_db"
                ) as move:
                    if outcome is None:
                        move.return_value = None
                    else:
                        move.side_effect = outcome

                    response = self.client.post(
                        "/appointments/42/reschedule",
                        json=self.payload,
                    )

                self.assertEqual(response.status_code, 409)
                self.assertEqual(
                    response.headers["cache-control"], "no-store"
                )

    def test_invalid_payload_never_reaches_database(self):
        invalid_payloads = [
            {
                **self.payload,
                "starts_at": "2030-01-07T10:30:00",
            },
            {
                **self.payload,
                "expected_starts_at": "2030-01-07T10:00:00",
            },
            {**self.payload, "unexpected": True},
            {"starts_at": self.payload["starts_at"]},
        ]

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with patch(
                    "main.reschedule_appointment_in_db"
                ) as move:
                    response = self.client.post(
                        "/appointments/42/reschedule",
                        json=payload,
                    )

                self.assertEqual(response.status_code, 422)
                move.assert_not_called()

    def test_rescheduling_requires_login(self):
        app.dependency_overrides.pop(require_staff_change, None)

        with patch("main.reschedule_appointment_in_db") as move:
            response = self.client.post(
                "/appointments/42/reschedule",
                json=self.payload,
            )

        self.assertEqual(response.status_code, 401)
        move.assert_not_called()

    def test_invalid_slot_returns_422(self):
        with patch(
            "main.reschedule_appointment_in_db",
            side_effect=ValueError(
                "Η νέα ώρα είναι εκτός διαθέσιμου ωραρίου."
            ),
        ):
            response = self.client.post(
                "/appointments/42/reschedule",
                json=self.payload,
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.headers["cache-control"], "no-store"
        )