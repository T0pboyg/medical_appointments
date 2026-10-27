import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from auth import require_staff
from main import app


class AppointmentHistoryApiTests(unittest.TestCase):
    def setUp(self):
        self.previous_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[require_staff] = lambda: {
            "subject": "synthetic-staff"
        }
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.previous_overrides)

    def test_history_returns_events_and_uses_pagination(self):
        payload = {
            "events": [
                {
                    "id": 100,
                    "occurred_at": "2030-01-01T10:00:00+00:00",
                    "actor_issuer": "synthetic-issuer",
                    "actor_subject": "synthetic-staff",
                    "action": "appointment.rescheduled",
                    "previous_starts_at": "2030-01-07T08:00:00+00:00",
                    "new_starts_at": "2030-01-07T08:30:00+00:00",
                }
            ],
            "page": 2,
            "page_size": 25,
            "has_more": False,
        }

        with patch(
            "main.get_appointment_history_from_db",
            return_value=payload,
        ) as read:
            response = self.client.get(
                "/appointments/42/history",
                params={"page": 2},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)
        self.assertEqual(
            response.headers["cache-control"], "no-store"
        )
        read.assert_called_once_with(
            42, page=2, page_size=25
        )

    def test_missing_appointment_returns_404(self):
        with patch(
            "main.get_appointment_history_from_db",
            return_value=None,
        ):
            response = self.client.get(
                "/appointments/42/history"
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.headers["cache-control"], "no-store"
        )

    def test_invalid_parameters_never_reach_database(self):
        urls = [
            "/appointments/0/history",
            "/appointments/42/history?page=0",
            "/appointments/42/history?page_size=101",
        ]

        for url in urls:
            with self.subTest(url=url):
                with patch(
                    "main.get_appointment_history_from_db"
                ) as read:
                    response = self.client.get(url)

                self.assertEqual(response.status_code, 422)
                read.assert_not_called()

    def test_history_requires_staff_login(self):
        app.dependency_overrides.pop(require_staff, None)

        with patch(
            "main.get_appointment_history_from_db"
        ) as read:
            response = self.client.get(
                "/appointments/42/history"
            )

        self.assertEqual(response.status_code, 401)
        read.assert_not_called()