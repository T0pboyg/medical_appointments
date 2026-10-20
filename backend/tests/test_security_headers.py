import unittest

from fastapi.testclient import TestClient

from main import app


class SecurityHeaderTests(unittest.TestCase):
    def test_headers_on_success_and_errors(self):
        expected = {
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "X-Frame-Options": "DENY",
            "Permissions-Policy": (
                "camera=(), microphone=(), geolocation=()"
            ),
        }

        with TestClient(app) as client:
            responses = [
                (client.get("/"), 200),
                (client.get("/availability?date=invalid"), 422),
                (
                    client.post(
                        "/appointments",
                        content=b"x" * (16 * 1024 + 1),
                        headers={"Content-Type": "application/json"},
                    ),
                    413,
                ),
            ]

        for response, status in responses:
            with self.subTest(status=status):
                self.assertEqual(response.status_code, status)

                for name, value in expected.items():
                    self.assertEqual(
                        response.headers.get(name),
                        value,
                    )