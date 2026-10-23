import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import psycopg
from psycopg.conninfo import make_conninfo

from database import cancel_appointment_in_db, find_staff_appointments


class StaffAssistantDatabaseTests(unittest.TestCase):
    def test_snapshot_guard_rejects_changed_patient_and_replay(self):
        test_url = make_conninfo(os.environ['DATABASE_URL'], dbname='appointments_migration_test')
        marker = f'Staff Assistant Synthetic {uuid4()}'
        start = datetime.now(timezone.utc) + timedelta(days=120, microseconds=123)
        with psycopg.connect(test_url, autocommit=True) as connection:
            appointment_id = connection.execute(
                'INSERT INTO appointments (patient_name, patient_phone, patient_amka, starts_at) VALUES (%s, %s, %s, %s) RETURNING id',
                (marker, '6900000000', '00000000000', start),
            ).fetchone()[0]
            try:
                with patch.dict(os.environ, {'DATABASE_URL': test_url}):
                    found = find_staff_appointments(appointment_id=appointment_id, future_only=True)
                    self.assertEqual(set(found[0]), {'id', 'patient_name', 'starts_at'})
                    connection.execute('UPDATE appointments SET patient_name = %s WHERE id = %s', (marker + ' changed', appointment_id))
                    self.assertIsNone(cancel_appointment_in_db(appointment_id, 'test', 'staff', uuid4(), expected_starts_at=start, expected_patient_name=marker))
                    self.assertEqual(connection.execute('SELECT count(*) FROM audit_events WHERE appointment_id = %s', (appointment_id,)).fetchone()[0], 0)
                    connection.execute('UPDATE appointments SET patient_name = %s WHERE id = %s', (marker, appointment_id))
                    self.assertIsNone(cancel_appointment_in_db(appointment_id, 'test', 'staff', uuid4(), expected_starts_at=start + timedelta(minutes=30), expected_patient_name=marker))
                    self.assertIsNotNone(cancel_appointment_in_db(appointment_id, 'test', 'staff', uuid4(), expected_starts_at=start, expected_patient_name=marker))
                    self.assertIsNone(cancel_appointment_in_db(appointment_id, 'test', 'staff', uuid4(), expected_starts_at=start, expected_patient_name=marker))
                    self.assertEqual(connection.execute("SELECT count(*) FROM audit_events WHERE appointment_id = %s AND action = 'appointment.cancelled'", (appointment_id,)).fetchone()[0], 1)
            finally:
                connection.execute('DELETE FROM audit_events WHERE appointment_id = %s', (appointment_id,))
                connection.execute('DELETE FROM appointments WHERE id = %s', (appointment_id,))
