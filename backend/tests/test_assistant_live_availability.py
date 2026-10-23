import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo
from psycopg import OperationalError

from assistant_service import answer_question
from assistant_symptoms import symptom_information


class AssistantImprovementTests(unittest.IsolatedAsyncioTestCase):
    def test_fever_and_natural_headache_use_relevant_sources(self):
        answer = symptom_information('εχω πυρετο και ποναει το κεφαλι μου για 3 μερες')
        ids = {source['id'] for source in answer['sources']}
        self.assertIn('headache-original', ids)
        self.assertNotIn('sore-throat-original', ids)
        self.assertNotIn('πονόλαιμος', answer['answer'])
        self.assertIn('3 μέρες', answer['answer'])
        self.assertIn('Λυπάμαι', answer['answer'])

    async def test_next_week_uses_live_slots_without_model(self):
        from assistant_booking import booking_response
        now = datetime(2026, 10, 24, 23, tzinfo=ZoneInfo('Europe/Athens'))
        with patch('assistant_booking.get_available_slots', return_value=['09:00', '10:30']):
            answer = booking_response('θελω ραντεβου την επομενη εβδομαδα', now=now)
        self.assertEqual(answer['status'], 'booking_availability')
        self.assertIn('26/10/2026', answer['answer'])
        self.assertIn('01/11/2026', answer['answer'])
        self.assertIn('10:30', answer['answer'])
        self.assertLessEqual(sum(len(day['times']) for day in answer['availability']), 6)
        self.assertIn('Δεν έχει δημιουργηθεί', answer['answer'])

    async def test_booking_lookup_is_integrated(self):
        expected = {'status': 'booking_availability', 'answer': '09:00', 'sources': []}
        with patch('assistant_service.booking_response', return_value=expected):
            self.assertEqual(await answer_question('θελω ραντεβου την επομενη εβδομαδα'), expected)

    def test_ambiguous_date_does_not_check_random_day(self):
        from assistant_booking import booking_response
        with patch('assistant_booking.get_available_slots', side_effect=AssertionError('Unexpected lookup')):
            answer = booking_response('υπαρχει διαθεσιμο ραντεβου τη δευτερα στις 10:00')
        self.assertEqual(answer['status'], 'booking_help')
        self.assertIn('ημερομηνία', answer['answer'])

    def test_no_slots_is_reported_without_inventing_alternatives(self):
        from assistant_booking import booking_response
        with patch('assistant_booking.get_available_slots', return_value=[]):
            answer = booking_response('θελω ραντεβου αυριο')
        self.assertEqual(answer['availability'], [])
        self.assertIn('Δεν βρήκα', answer['answer'])

    def test_lookup_failure_is_not_reported_as_no_slots(self):
        from assistant_booking import booking_response
        with patch('assistant_booking.get_available_slots', side_effect=OperationalError('offline')):
            answer = booking_response('θελω ραντεβου αυριο')
        self.assertEqual(answer['status'], 'booking_unavailable')
        self.assertNotIn('Δεν βρήκα', answer['answer'])

    def test_extra_time_constraints_are_not_silently_ignored(self):
        from assistant_booking import booking_response
        for question in (
            'θελω ραντεβου την επομενη εβδομαδα μονο απογευμα',
            'θελω ραντεβου αυριο μετα τις δεκα',
            'θελω ραντεβου αυριο η την επομενη εβδομαδα',
        ):
            with self.subTest(question=question), patch('assistant_booking.get_available_slots', side_effect=AssertionError('Unexpected lookup')):
                self.assertEqual(booking_response(question)['status'], 'booking_help')

    def test_shared_calculation_excludes_bookings_and_partial_blocks(self):
        from availability_service import get_available_slots
        tz = ZoneInfo('Europe/Athens')
        day = datetime(2026, 10, 26, tzinfo=tz).date()
        slots = get_available_slots(
            day, now=datetime(2026, 10, 24, tzinfo=tz),
            booked_reader=lambda _: ['09:00'],
            blocks_reader=lambda _: [{
                'starts_at': datetime(2026, 10, 26, 10, 15, tzinfo=tz),
                'ends_at': datetime(2026, 10, 26, 10, 45, tzinfo=tz),
            }],
        )
        self.assertNotIn('09:00', slots)
        self.assertNotIn('10:00', slots)
        self.assertNotIn('10:30', slots)
        self.assertIn('09:30', slots)
        self.assertIn('11:00', slots)

    def test_relative_dates_use_athens_and_next_week_crosses_year(self):
        from assistant_booking import booking_response
        from datetime import timezone
        now = datetime(2026, 12, 27, 23, 30, tzinfo=timezone.utc)
        with patch('assistant_booking.get_available_slots', return_value=[]):
            answer = booking_response('θελω ραντεβου την επομενη εβδομαδα', now=now)
        # Already Monday 28 December in Athens: next Monday is 4 January.
        self.assertIn('04/01/2027', answer['answer'])
        self.assertIn('10/01/2027', answer['answer'])

    async def test_symptoms_take_priority_over_live_calendar(self):
        with patch('assistant_service.booking_response', side_effect=AssertionError('No calendar lookup')):
            answer = await answer_question('έχω πυρετό και πονάει το κεφάλι μου, θέλω ραντεβού αύριο')
        self.assertEqual(answer['status'], 'symptom_information')
