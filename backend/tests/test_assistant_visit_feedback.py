import json
import unittest
from unittest.mock import patch

import httpx

from assistant_knowledge import retrieve
from assistant_service import answer_question


class VisitFeedbackTests(unittest.IsolatedAsyncioTestCase):
    def test_bringing_still_returns_focused_visit_source(self):
        doc = retrieve('Τι πρέπει να φέρω μαζί μου στο πρώτο ραντεβού;')[0]
        self.assertEqual(doc['id'], 'visit-preparation')
        self.assertIn('λίστα των φαρμάκων', doc['text'])

    def test_describing_and_recording_have_relevant_evidence(self):
        for question in (
            'Πώς να εξηγήσω στον γιατρό τα συμπτώματά μου;',
            'Τι πληροφορίες να σημειώσω πριν από την επίσκεψη;',
            'Πώς να περιγράψω στον γιατρό τι αισθάνομαι;',
            'Τι να γράψω πριν το ραντεβού;',
        ):
            with self.subTest(question=question):
                docs = retrieve(question)
                self.assertTrue(docs)
                self.assertEqual(docs[0]['id'], 'visit-communication')
                self.assertIn('πότε ξεκίνησαν', docs[0]['text'])

    async def test_communication_passes_through_grounded_service(self):
        async def respond(request):
            payload = json.loads(request.content)
            self.assertIn('visit-communication', payload['format']['properties']['selected_ids']['items']['enum'])
            return httpx.Response(200, json={'done_reason': 'stop', 'message': {
                'content': '{"selected_ids":["visit-communication"]}'}})
        for question in ('Πώς να εξηγήσω στον γιατρό τα συμπτώματά μου;', 'Τι πληροφορίες να σημειώσω πριν από την επίσκεψη;'):
            with self.subTest(question=question):
                async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
                    answer = await answer_question(question, client)
                self.assertEqual(answer['status'], 'grounded')
                self.assertIn('πότε ξεκίνησαν', answer['answer'])

    async def test_unrelated_explanations_and_medication_stay_out_of_scope(self):
        self.assertEqual(retrieve('Πώς να εξηγήσω τη δουλειά μου;'), [])
        self.assertEqual(retrieve('Τι να σημειώσω πριν από τη συνέντευξη;'), [])
        with patch('assistant_service.httpx.AsyncClient', side_effect=AssertionError('No model')):
            self.assertEqual((await answer_question('Τι φάρμακο να πάρω πριν την επίσκεψη;'))['status'], 'insufficient')
