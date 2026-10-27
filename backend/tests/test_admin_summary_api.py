import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from auth import require_staff
from main import app


class AdminSummaryApiTests(unittest.TestCase):
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

    def test_summary_returns_only_counts_and_next_time(self):
        payload = {
            "date": "2030-01-07",
            "appointments_count": 5,
            "next_starts_at": "2030-01-07T10:30:00+02:00",
            "available_slots_count": 8,
            "no_show_count": 1,
        }

        with patch(
            "main.get_admin_summary",
            return_value=payload,
        ) as read:
            response = self.client.get("/appointments/summary")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)
        self.assertEqual(
            response.headers["cache-control"], "no-store"
        )
        read.assert_called_once_with()

    def test_summary_handles_no_next_appointment(self):
        payload = {
            "date": "2030-01-07",
            "appointments_count": 0,
            "next_starts_at": None,
            "available_slots_count": 16,
            "no_show_count": 0,
        }

        with patch(
            "main.get_admin_summary",
            return_value=payload,
        ):
            response = self.client.get("/appointments/summary")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["next_starts_at"])

    def test_summary_requires_staff_login(self):
        app.dependency_overrides.pop(require_staff, None)

        with patch("main.get_admin_summary") as read:
            response = self.client.get("/appointments/summary")

        self.assertEqual(response.status_code, 401)
        read.assert_not_called()