import os
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo

import psycopg
from fastapi.testclient import TestClient
from psycopg.conninfo import make_conninfo

from auth import require_staff
from database import get_appointments_from_db, get_appointments_page_from_db, get_appointment_details_from_db
from main import app


class AdminFilterRouteTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[require_staff] = lambda: {'subject': 'synthetic-staff'}
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.pop(require_staff, None)

    def test_default_is_clinic_today(self):
        # UTC is still the previous day; Athens has already crossed midnight.
        with patch('main.datetime') as clock, patch('main.get_appointments_from_db', return_value=[]) as read:
            clock.now.return_value = datetime(2030, 1, 5, 0, 30, tzinfo=ZoneInfo('Europe/Athens'))
            response = self.client.get('/appointments')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        read.assert_called_once_with(appointment_date=date(2030, 1, 5), patient_amka=None)

    def test_date_and_amka_reach_database_together(self):
        with patch('main.get_appointments_from_db', return_value=[]) as read:
            response = self.client.get('/appointments', params={'appointment_date': '2030-01-07', 'patient_AMKA': '00000000000'})
        self.assertEqual(response.status_code, 200)
        read.assert_called_once_with(appointment_date=date(2030, 1, 7), patient_amka='00000000000')

    def test_bad_filter_never_reaches_database(self):
        for params in ({'appointment_date': 'not-a-date'}, {'patient_AMKA': '123'}, {'patient_AMKA': 'abcdefghijk'}):
            with self.subTest(params=params), patch('main.get_appointments_from_db') as read:
                self.assertEqual(self.client.get('/appointments', params=params).status_code, 422)
                read.assert_not_called()

    def test_page_parameters_and_private_details(self):
        payload = {'items': [], 'page': 2, 'page_size': 25, 'has_more': False}
        with patch('main.get_appointments_page_from_db', return_value=payload) as read:
            response = self.client.get('/appointments/page', params={
                'appointment_date': '2030-01-07', 'page': 2, 'patient_AMKA': '00000000000'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        read.assert_called_once_with(appointment_date=date(2030, 1, 7), patient_amka='00000000000', page=2, page_size=25)
        with patch('main.get_appointment_details_from_db', return_value={'id': 1, 'patient_phone': '6900000000'}) as read:
            response = self.client.get('/appointments/1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        read.assert_called_once_with(1)

    def test_invalid_page_and_missing_details(self):
        for params in ({'page': 0}, {'page_size': 101}, {'appointment_date': '9999-12-31'}):
            with self.subTest(params=params), patch('main.get_appointments_page_from_db') as read:
                self.assertEqual(self.client.get('/appointments/page', params=params).status_code, 422)
                read.assert_not_called()
        with patch('main.get_appointment_details_from_db', return_value=None):
            response = self.client.get('/appointments/999')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers['cache-control'], 'no-store')

    def test_page_and_details_require_staff(self):
        app.dependency_overrides.pop(require_staff)
        for url in ('/appointments/page', '/appointments/1'):
            with self.subTest(url=url), patch('main.get_appointments_page_from_db') as page, patch('main.get_appointment_details_from_db') as details:
                self.assertEqual(self.client.get(url).status_code, 401)
                page.assert_not_called()
                details.assert_not_called()


class AdminFilterDatabaseTests(unittest.TestCase):
    def test_pages_are_disjoint_and_details_are_separate(self):
        test_url = make_conninfo(os.environ['DATABASE_URL'], dbname='appointments_migration_test')
        amka = str(uuid4().int % 10**11).zfill(11)
        day = date(2032, 2, 9)
        start = datetime(2032, 2, 9, 9, tzinfo=ZoneInfo('Europe/Athens')) + timedelta(microseconds=uuid4().int % 900000 + 1)
        ids = []
        with psycopg.connect(test_url, autocommit=True) as connection:
            try:
                for index in range(3):
                    ids.append(connection.execute(
                        'INSERT INTO appointments (patient_name, patient_phone, patient_amka, starts_at) VALUES (%s,%s,%s,%s) RETURNING id',
                        ('Synthetic Pagination', '6900000000', amka, start + timedelta(minutes=30 * index))).fetchone()[0])
                with patch.dict(os.environ, {'DATABASE_URL': test_url}):
                    first = get_appointments_page_from_db(appointment_date=day, patient_amka=amka, page_size=2)
                    second = get_appointments_page_from_db(appointment_date=day, patient_amka=amka, page_size=2, page=2)
                    details = get_appointment_details_from_db(ids[0])
                self.assertEqual([row['id'] for row in first['items']], ids[:2])
                self.assertEqual([row['id'] for row in second['items']], ids[2:])
                self.assertTrue(first['has_more'])
                self.assertFalse(second['has_more'])
                for row in first['items'] + second['items']:
                    self.assertNotIn('patient_phone', row)
                    self.assertNotIn('patient_AMKA', row)
                self.assertEqual(details['patient_AMKA'], amka)
                self.assertEqual(details['patient_phone'], '6900000000')
            finally:
                connection.execute('DELETE FROM appointments WHERE id = ANY(%s)', (ids,))

    def test_clinic_day_bounds_and_amka_on_both_dst_transitions(self):
        test_url = make_conninfo(os.environ['DATABASE_URL'], dbname='appointments_migration_test')
        tz = ZoneInfo('Europe/Athens')
        marker = f'Admin Filter Synthetic {uuid4()}'
        with psycopg.connect(test_url, autocommit=True) as connection:
            for day in (date(2026, 3, 29), date(2026, 10, 25)):
                start = datetime.combine(day, datetime.min.time(), tzinfo=tz).astimezone(timezone.utc)
                end = datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=tz).astimezone(timezone.utc)
                offset = timedelta(microseconds=uuid4().int % 900000 + 1)
                ids = []
                try:
                    for stamp, amka in ((start + offset, '00000000000'), (end - offset, '00000000000'), (end + offset, '00000000000'), (start + timedelta(hours=1) + offset, '11111111111')):
                        ids.append(connection.execute('INSERT INTO appointments (patient_name, patient_phone, patient_amka, starts_at) VALUES (%s,%s,%s,%s) RETURNING id', (marker, '6900000000', amka, stamp)).fetchone()[0])
                    with patch.dict(os.environ, {'DATABASE_URL': test_url}):
                        rows = get_appointments_from_db(appointment_date=day, patient_amka='00000000000')
                    self.assertTrue(set(ids[:2]).issubset({r['id'] for r in rows}))
                    self.assertNotIn(ids[2], {r['id'] for r in rows})
                    self.assertNotIn(ids[3], {r['id'] for r in rows})
                    self.assertEqual([r['starts_at'] for r in rows], sorted(r['starts_at'] for r in rows))
                finally:
                    connection.execute('DELETE FROM appointments WHERE id = ANY(%s)', (ids,))
