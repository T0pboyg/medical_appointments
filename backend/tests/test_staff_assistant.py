import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import require_staff


SESSION = {'issuer': 'test-issuer', 'subject': 'staff-a', 'csrf_token': 'test-csrf'}
NOW = datetime(2030, 1, 4, 12, tzinfo=ZoneInfo('Europe/Athens'))
APPOINTMENT = {'id': 42, 'patient_name': 'Δοκιμή Παπαδόπουλος', 'starts_at': NOW + timedelta(days=3)}


class StaffAssistantTests(unittest.TestCase):
    def test_day_resolution_is_explicit_and_rejects_conflicting_dates(self):
        from staff_assistant import resolve_day
        self.assertEqual(resolve_day('τη Δευτέρα', now=NOW), date(2030, 1, 7))
        self.assertEqual(resolve_day('στις 07/01/2030', now=NOW), date(2030, 1, 7))
        self.assertEqual(resolve_day('αύριο', now=NOW), date(2030, 1, 5))
        self.assertIsNone(resolve_day('στις 07/01', now=NOW))
        self.assertIsNone(resolve_day('αύριο ή τη Δευτέρα', now=NOW))
        self.assertIsNone(resolve_day('την επόμενη εβδομάδα', now=NOW))
        self.assertIsNone(resolve_day('Δευτέρα 08/01/2030', now=NOW))
        self.assertIsNone(resolve_day('07/01/2030 ή 08/01', now=NOW))
        self.assertIsNone(resolve_day('τη Δευτέρα σε δύο εβδομάδες', now=NOW))

    def test_explicit_id_does_not_override_invalid_date_constraint(self):
        from staff_assistant import prepare_response
        for message in ('ακύρωσε το ραντεβού #42 στις 31/02/2030', 'ακύρωσε το ραντεβού #42 στις 7 Ιανουαρίου 2030'):
            with self.subTest(message=message), patch('staff_assistant.find_staff_appointments', side_effect=AssertionError('Do not ignore a date constraint')):
                result = prepare_response(message, {'action': 'cancel', 'patient_name': None, 'appointment_id': 42}, SESSION, now=NOW)
            self.assertFalse(result.get('appointments'))

    def test_reading_all_appointments_of_one_day_is_allowed(self):
        from staff_assistant import prepare_response
        with patch('staff_assistant.find_staff_appointments', return_value=[APPOINTMENT]):
            result = prepare_response('δείξε όλα τα ραντεβού αύριο', {'action': 'list', 'patient_name': None, 'appointment_id': None}, SESSION, now=NOW)
        self.assertEqual(result['appointments'][0]['id'], 42)

    def test_unsupported_time_constraints_require_clarification(self):
        from staff_assistant import prepare_response
        for message in ('ελεύθερες ώρες αύριο μετά τις 14:00', 'ελεύθερες ώρες αύριο το πρωί'):
            with self.subTest(message=message), patch('staff_assistant.get_available_slots', side_effect=AssertionError('Do not ignore time constraint')):
                result = prepare_response(message, {'action': 'availability', 'patient_name': None, 'appointment_id': None}, SESSION, now=NOW)
            self.assertIn('ώρας', result['answer'])

    def test_preview_token_is_session_bound_and_expires(self):
        from staff_assistant import make_preview, read_preview
        from fastapi import HTTPException
        with patch.dict('os.environ', {'API_PROXY_SECRET': 'test-signing-secret'}):
            token = make_preview(APPOINTMENT, SESSION, timestamp=100)
            self.assertEqual(read_preview(token, SESSION, timestamp=101)['id'], 42)
            for bad_token, session, timestamp in (
                (token + 'x', SESSION, 101),
                (token, {**SESSION, 'subject': 'staff-b'}, 101),
                (token, {**SESSION, 'csrf_token': 'new-session'}, 101),
                (token, SESSION, 401),
            ):
                with self.subTest(timestamp=timestamp, session=session), self.assertRaises(HTTPException):
                    read_preview(bad_token, session, timestamp=timestamp)

    def test_staff_routes_require_login(self):
        from staff_assistant import router
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as client:
            for path, body in (('/staff-assistant/chat', {'message': 'δείξε τα ραντεβού αύριο'}), ('/staff-assistant/confirm', {'token': 'invalid'})):
                self.assertEqual(client.post(path, json=body).status_code, 401)

    def test_staff_routes_require_origin_and_csrf_even_for_chat(self):
        from staff_assistant import router
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[require_staff] = lambda: SESSION
        with TestClient(app) as client:
            for headers in ({}, {'Origin': 'http://evil.example', 'X-CSRF-Token': 'test-csrf'}, {'Origin': 'http://localhost:5173'}):
                self.assertEqual(client.post('/staff-assistant/chat', json={'message': 'δείξε τα ραντεβού αύριο'}, headers=headers).status_code, 403)

    def test_cancel_command_only_returns_candidates_and_tokens(self):
        from staff_assistant import prepare_response
        with patch('staff_assistant.find_staff_appointments', return_value=[APPOINTMENT, {**APPOINTMENT, 'id': 43}]), patch('staff_assistant.cancel_appointment_in_db', side_effect=AssertionError('No write before confirmation')), patch.dict('os.environ', {'API_PROXY_SECRET': 'test-signing-secret'}):
            result = prepare_response('ακύρωσε της Δευτέρας του Παπαδόπουλος', {'action': 'cancel', 'patient_name': 'Παπαδόπουλος', 'appointment_id': None}, SESSION, now=NOW)
        self.assertEqual(len(result['appointments']), 2)
        self.assertTrue(all(item['confirmation_token'] for item in result['appointments']))
        self.assertEqual(set(result['appointments'][0]), {'id', 'patient_name', 'starts_at', 'confirmation_token'})

    def test_invented_patient_or_id_does_not_trigger_search(self):
        from staff_assistant import prepare_response
        for intent in (
            {'action': 'cancel', 'patient_name': 'Άλλος', 'appointment_id': None},
            {'action': 'cancel', 'patient_name': None, 'appointment_id': 999},
        ):
            with self.subTest(intent=intent), patch('staff_assistant.find_staff_appointments', side_effect=AssertionError('No invented lookup')):
                result = prepare_response('ακύρωσε της Δευτέρας του Παπαδόπουλος', intent, SESSION, now=NOW)
            self.assertFalse(result.get('appointments'))

    def test_missing_patient_never_cancels_a_whole_day(self):
        from staff_assistant import prepare_response
        with patch('staff_assistant.find_staff_appointments', side_effect=AssertionError('No bulk lookup')):
            result = prepare_response('ακύρωσε όλα τα ραντεβού αύριο', {'action': 'cancel', 'patient_name': None, 'appointment_id': None}, SESSION, now=NOW)
        self.assertFalse(result.get('appointments'))

    def test_confirm_calls_existing_audited_cancellation_with_snapshot(self):
        from staff_assistant import router, make_preview
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[require_staff] = lambda: SESSION
        headers = {'Origin': 'http://localhost:5173', 'X-CSRF-Token': 'test-csrf'}
        with patch.dict('os.environ', {'API_PROXY_SECRET': 'test-signing-secret'}), TestClient(app) as client:
            token = make_preview(APPOINTMENT, SESSION)
            with patch('staff_assistant.cancel_appointment_in_db', return_value={'id': 42, 'cancelled_at': NOW}) as cancel:
                response = client.post('/staff-assistant/confirm', json={'token': token}, headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers['cache-control'], 'no-store')
            self.assertEqual(cancel.call_args.args[:3], (42, 'test-issuer', 'staff-a'))
            self.assertEqual(cancel.call_args.kwargs['expected_starts_at'], APPOINTMENT['starts_at'])
            self.assertEqual(cancel.call_args.kwargs['expected_patient_name'], APPOINTMENT['patient_name'])
            with patch('staff_assistant.cancel_appointment_in_db', return_value=None):
                self.assertEqual(client.post('/staff-assistant/confirm', json={'token': token}, headers=headers).status_code, 409)
            with patch('staff_assistant.cancel_appointment_in_db', side_effect=AssertionError('No write from forged token')):
                self.assertEqual(client.post('/staff-assistant/confirm', json={'token': token + 'x'}, headers=headers).status_code, 409)
