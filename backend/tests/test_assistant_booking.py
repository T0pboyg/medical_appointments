import unittest
from unittest.mock import patch

from assistant_service import answer_question


class BookingHelpTests(unittest.IsolatedAsyncioTestCase):
    async def test_booking_questions_return_form_guidance_without_model(self):
        for question in (
            'Πώς κλείνω ραντεβού;',
            'Υπάρχει διαθέσιμο ραντεβού τη Δευτέρα στις 10:00;',
            'Θέλω ραντεβού στις 12/11, μπορείς να το κλείσεις;',
        ):
            with self.subTest(question=question):
                with patch('assistant_service.httpx.AsyncClient', side_effect=AssertionError('Unexpected LLM call')):
                    answer = await answer_question(question)
                self.assertEqual(answer['status'], 'booking_help')
                self.assertIn('φόρμα', answer['answer'])
                self.assertIn('Δεν έχει δημιουργηθεί', answer['answer'])
                self.assertEqual(answer['actions'], [{
                    'type': 'booking_form',
                    'label': 'Μετάβαση στην κράτηση',
                    'href': '/#appointment-form',
                }])
                self.assertEqual(answer['sources'], [])

    async def test_emergency_takes_priority_over_booking(self):
        answer = await answer_question('Έχω πόνο στο στήθος, θέλω να κλείσω ραντεβού')
        self.assertEqual(answer['status'], 'urgent')
        self.assertFalse(answer.get('actions'))

    async def test_cost_is_not_invented(self):
        answer = await answer_question('Πόσο κοστίζει το ραντεβού;')
        self.assertEqual(answer['status'], 'insufficient')

    async def test_preparation_still_uses_medical_sources(self):
        with patch('assistant_service.retrieve', return_value=[]) as retrieve:
            answer = await answer_question('Τι να φέρω στο ραντεβού;')
        retrieve.assert_called_once()
        self.assertEqual(answer['status'], 'insufficient')
