import json
import unittest

import httpx

from assistant_service import AssistantUnavailable
from staff_assistant_intent import extract_intent


class IntentTests(unittest.IsolatedAsyncioTestCase):
    async def test_model_only_receives_command_and_returns_structured_intent(self):
        async def respond(request):
            payload = json.loads(request.content)
            self.assertFalse(payload['think'])
            self.assertEqual(json.loads(payload['messages'][1]['content']), {'command': 'Ακύρωσε το ραντεβού #42'})
            return httpx.Response(200, json={'done_reason': 'stop', 'message': {'content': json.dumps({
                'action': 'cancel', 'patient_name': None, 'appointment_id': 42})}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            self.assertEqual((await extract_intent('Ακύρωσε το ραντεβού #42', client))['appointment_id'], 42)

    async def test_unknown_tools_extra_fields_and_incomplete_outputs_are_rejected(self):
        for content, reason in (
            ({'action': 'sql', 'patient_name': None, 'appointment_id': None}, 'stop'),
            ({'action': 'cancel', 'patient_name': None, 'appointment_id': True}, 'stop'),
            ({'action': 'cancel', 'patient_name': None, 'appointment_id': 42, 'sql': 'DELETE'}, 'stop'),
            ({'action': 'cancel', 'patient_name': None, 'appointment_id': 42}, 'length'),
        ):
            async def respond(request):
                return httpx.Response(200, json={'done_reason': reason, 'message': {'content': json.dumps(content)}})
            with self.subTest(content=content), self.assertRaises(AssistantUnavailable):
                async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
                    await extract_intent('εντολή', client)
