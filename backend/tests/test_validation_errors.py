import unittest

from fastapi.testclient import TestClient
from rate_limits import require_booking_limit

from main import app


class ValidationErrorTests(unittest.TestCase):
    def test_validation_response_does_not_echo_input(self):
        sensitive_value = "PRIVATE-TEST-VALUE"

        with TestClient(app) as client:
            response = client.get(
                "/availability",
                params={"date": sensitive_value},
            )

        self.assertEqual(response.status_code, 422)
        self.assertNotIn(sensitive_value, response.text)

        for error in response.json()["detail"]:
            self.assertNotIn("input", error)
            self.assertNotIn("ctx", error)

        self.assertEqual(
            response.headers.get("cache-control"),
            "no-store",
        )


    def test_invalid_phone_is_not_echoed(self):
        sensitive_phone = "PRIVATE-PHONE-VALUE"
        previous_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[require_booking_limit] = lambda: None

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/appointments",
                    json={
                        "patient_name": "Validation Test",
                        "patient_phone": sensitive_phone,
                        "patient_AMKA": "00000000000",
                        "starts_at": "2030-01-07T10:00:00+02:00",
                    },
                )
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(previous_overrides)

        self.assertEqual(response.status_code, 422)
        self.assertNotIn(sensitive_phone, response.text)
        self.assertTrue(
            any(
                error["loc"] == ["body", "patient_phone"]
                for error in response.json()["detail"]
            )
        )