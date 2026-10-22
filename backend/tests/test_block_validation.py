import unittest

from pydantic import ValidationError

from availability_blocks import AvailabilityBlockCreate


class BlockValidationTests(unittest.TestCase):
    def test_invalid_intervals_and_reasons_are_rejected(self):
        valid = {
            "starts_at": "2099-01-15T09:00:00+02:00",
            "ends_at": "2099-01-15T17:00:00+02:00",
            "reason": "Άδεια",
        }

        invalid_cases = [
            {"starts_at": "2099-01-15T09:00:00"},
            {"ends_at": "2099-01-15T17:00:00"},
            {"ends_at": valid["starts_at"]},
            {"ends_at": "2099-01-15T08:00:00+02:00"},
            {"reason": "   "},
            {"reason": "x" * 201},
            {"unexpected": True},
        ]

        for changes in invalid_cases:
            with self.subTest(changes=changes):
                with self.assertRaises(ValidationError):
                    AvailabilityBlockCreate(**(valid | changes))

    def test_valid_reason_is_trimmed(self):
        block = AvailabilityBlockCreate(
            starts_at="2099-01-15T09:00:00+02:00",
            ends_at="2099-01-15T17:00:00+02:00",
            reason="  Άδεια  ",
        )

        self.assertEqual(block.reason, "Άδεια")