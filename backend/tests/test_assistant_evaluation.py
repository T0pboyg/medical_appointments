import json
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from assistant_service import answer_question

CASES = json.loads((Path(__file__).parent / 'fixtures' / 'public_assistant_questions.json').read_text(encoding='utf-8'))


class PublicEvaluationTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_thirty_questions_have_expected_routes_and_boundaries(self):
        async def respond(request):
            payload = json.loads(request.content)
            ids = payload['format']['properties']['selected_ids']['items']['enum']
            return httpx.Response(200, json={'done_reason': 'stop', 'message': {'content': json.dumps({'selected_ids': ids[:1]})}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            for case in CASES:
                with self.subTest(number=case['number'], question=case['question']), patch('assistant_booking.get_available_slots', return_value=['09:00']):
                    answer = await answer_question(case['question'], client)
                    self.assertEqual(answer['status'], case['expected_status'])
                    if 17 <= case['number'] <= 20:
                        self.assertIn('112', answer['answer'])
                        self.assertFalse(answer.get('actions'))
                    if case['number'] == 6:
                        self.assertIn('Μην διακόπτετε', answer['answer'])
                    if case['number'] == 7:
                        self.assertIn('δεν σημαίνει απαραίτητα', answer['answer'])
                    if case['number'] == 10:
                        self.assertIn('πότε ξεκίνησαν', answer['answer'])
                    if case['number'] == 30:
                        self.assertIn('Μην γράφεις', answer['answer'])
