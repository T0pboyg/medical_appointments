import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from staff_assistant import prepare_response
from test_staff_assistant import SESSION


class StaffDateTests(unittest.TestCase):
    def test_next_week_in_natural_greek(self):
        from staff_assistant_intent import resolve_period
        now = datetime(2026, 10, 24, 12, tzinfo=ZoneInfo('Europe/Athens'))
        for phrase in ('της επόμενης εβδομάδας', 'την επομενη εβδομαδα', 'την επόμενη βδομάδα'):
            with self.subTest(phrase=phrase):
                self.assertEqual(resolve_period(phrase, now=now), (date(2026, 10, 26), date(2026, 11, 1)))

    def test_current_previous_week_and_specific_weekday(self):
        from staff_assistant_intent import resolve_period
        now = datetime(2026, 10, 24, 12, tzinfo=ZoneInfo('Europe/Athens'))
        for phrase, expected in (
            ('αυτής της εβδομάδας', (date(2026, 10, 19), date(2026, 10, 25))),
            ('την προηγούμενη εβδομάδα', (date(2026, 10, 12), date(2026, 10, 18))),
            ('την Τρίτη της επόμενης εβδομάδας', (date(2026, 10, 27), date(2026, 10, 27))),
        ):
            self.assertEqual(resolve_period(phrase, now=now), expected)

    def test_week_rollover_uses_athens_date(self):
        from staff_assistant_intent import resolve_period
        now = datetime(2026, 12, 27, 23, 30, tzinfo=timezone.utc)
        self.assertEqual(resolve_period('επόμενη εβδομάδα', now=now), (date(2027, 1, 4), date(2027, 1, 10)))

    def test_conflicting_constraints_still_require_clarification(self):
        from staff_assistant_intent import resolve_period
        for phrase in ('αύριο την επόμενη εβδομάδα', 'επόμενη εβδομάδα 07/01/2030', 'την επόμενη και την προηγούμενη εβδομάδα', 'Δευτέρα και Τρίτη της επόμενης εβδομάδας', 'σε δύο εβδομάδες'):
            with self.subTest(phrase=phrase):
                self.assertIsNone(resolve_period(phrase))

    def test_screenshot_command_returns_all_week_and_exact_dates(self):
        now = datetime(2026, 10, 24, 12, tzinfo=ZoneInfo('Europe/Athens'))
        def read_day(*, day, **kwargs):
            return [{'id': day.day * 10 + i, 'patient_name': 'Συνθετικό Παράδειγμα',
                     'starts_at': datetime(day.year, day.month, day.day, 9, i, tzinfo=now.tzinfo)} for i in range(5)]
        with patch('staff_assistant.find_staff_appointments', side_effect=read_day):
            answer = prepare_response('δειξε ολα τα ραντεβου της επομενης εβδομαδας', {'action': 'list', 'patient_name': None, 'appointment_id': None}, SESSION, now=now)
        self.assertEqual(len(answer['appointments']), 35)
        self.assertIn('26/10/2026', answer['answer'])
        self.assertIn('01/11/2026', answer['answer'])
        self.assertFalse(any('confirmation_token' in a for a in answer['appointments']))

    def test_weekly_availability_and_cancellation_are_bounded(self):
        now = datetime(2026, 10, 24, 12, tzinfo=ZoneInfo('Europe/Athens'))
        with patch('staff_assistant.get_available_slots', return_value=['09:00']):
            answer = prepare_response('ελεύθερες ώρες της επόμενης εβδομάδας', {'action': 'availability', 'patient_name': None, 'appointment_id': None}, SESSION, now=now)
        self.assertIn('26/10/2026', answer['answer'])
        self.assertIn('01/11/2026', answer['answer'])
        with patch('staff_assistant.find_staff_appointments', side_effect=AssertionError('Need a single cancellation day')):
            answer = prepare_response('ακύρωσε της επόμενης εβδομάδας του Δοκιμή', {'action': 'cancel', 'patient_name': 'Δοκιμή', 'appointment_id': None}, SESSION, now=now)
        self.assertFalse(answer['appointments'])
