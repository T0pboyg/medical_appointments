import unittest
import os
from datetime import datetime
from unittest.mock import patch, AsyncMock
from uuid import uuid4
from fastapi.testclient import TestClient
from fastapi import HTTPException
from psycopg.errors import UniqueViolation
from auth import require_staff_change
from main import app
from database import create_appointment_in_db

class StaffCreationTests(unittest.TestCase):
    def setUp(self):
        self.previous = app.dependency_overrides.copy()
        app.dependency_overrides[require_staff_change] = lambda: {"issuer":"test-issuer","subject":"test-staff"}
        self.client = TestClient(app)
        self.payload = {"patient_name":"Synthetic Patient","patient_phone":"6900000000","patient_AMKA":"00000000000","starts_at":"2030-01-07T10:00:00+02:00"}
    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.previous)
    def test_staff_creation_audits_actor(self):
        with patch("main.create_appointment_in_db", return_value={"id":42,"starts_at":datetime.fromisoformat(self.payload["starts_at"])}) as save:
            response=self.client.post("/staff/appointments",json=self.payload)
        self.assertEqual(response.status_code,201)
        self.assertEqual(response.json()["id"],42)
        self.assertNotIn("patient_AMKA",response.json())
        self.assertEqual(response.headers["cache-control"],"no-store")
        self.assertEqual(save.call_args.kwargs["actor_issuer"],"test-issuer")
        self.assertEqual(save.call_args.kwargs["actor_subject"],"test-staff")
        self.assertEqual(save.call_args.args[1],"+306900000000")
    def test_unauthorized_cannot_create(self):
        def reject(): raise HTTPException(401,"Login required")
        app.dependency_overrides[require_staff_change]=reject
        with patch("main.create_appointment_in_db") as save:
            response=self.client.post("/staff/appointments",json=self.payload)
        self.assertEqual(response.status_code,401)
        save.assert_not_called()
    def test_csrf_failure_cannot_create(self):
        def reject(): raise HTTPException(403,"Invalid CSRF")
        app.dependency_overrides[require_staff_change]=reject
        with patch("main.create_appointment_in_db") as save:
            response=self.client.post("/staff/appointments",json=self.payload)
        self.assertEqual(response.status_code,403)
        save.assert_not_called()
    def test_real_staff_dependency_rejects_missing_session(self):
        app.dependency_overrides.pop(require_staff_change, None)
        with patch("auth.get_staff_session", return_value=None), patch("main.create_appointment_in_db") as save:
            response=self.client.post("/staff/appointments",json=self.payload)
        self.assertEqual(response.status_code,401)
        save.assert_not_called()
    def test_real_staff_dependency_rejects_missing_csrf(self):
        app.dependency_overrides.pop(require_staff_change, None)
        session={"issuer":os.environ["OIDC_ISSUER"],"subject":"test-staff","csrf_token":"expected"}
        with patch("auth.get_staff_session",return_value=session), patch("auth.is_active_staff",new_callable=AsyncMock,return_value=True), patch("main.create_appointment_in_db") as save:
            response=self.client.post("/staff/appointments",json=self.payload,headers={"Origin":"http://localhost:5173"})
        self.assertEqual(response.status_code,403)
        save.assert_not_called()
    def test_conflict(self):
        with patch("main.create_appointment_in_db",side_effect=UniqueViolation("conflict")):
            response=self.client.post("/staff/appointments",json=self.payload)
        self.assertEqual(response.status_code,409)
    def test_weekend_rejected(self):
        with patch("main.create_appointment_in_db") as save:
            response=self.client.post("/staff/appointments",json={**self.payload,"starts_at":"2030-01-06T10:00:00+02:00"})
        self.assertEqual(response.status_code,400)
        save.assert_not_called()
    def test_invalid_patient_data(self):
        response=self.client.post("/staff/appointments",json={**self.payload,"patient_AMKA":"123"})
        self.assertEqual(response.status_code,422)

class StaffCreationTransactionTests(unittest.TestCase):
    @patch("database.psycopg.connect")
    def test_audit_uses_same_connection_and_no_patient_data(self, connect):
        cursor=connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect=[None,{"id":42}]
        token=uuid4()
        result=create_appointment_in_db("Synthetic","+306900000000","00000000000",datetime.fromisoformat("2030-01-07T10:00:00+02:00"),actor_issuer="issuer",actor_subject="staff",correlation_id=token)
        self.assertEqual(result["id"],42)
        connect.assert_called_once()
        sql,args=cursor.execute.call_args.args
        self.assertIn("INSERT INTO audit_events",sql)
        self.assertIn("appointment.created",sql)
        self.assertEqual(args,("issuer","staff",42,token))
        self.assertNotIn("Synthetic",str(args))

    @patch("database.psycopg.connect")
    def test_audit_failure_propagates_for_transaction_rollback(self, connect):
        connection=connect.return_value
        cursor=connection.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect=[None,{"id":42}]
        cursor.execute.side_effect=[None,None,None,RuntimeError("audit unavailable")]
        with self.assertRaisesRegex(RuntimeError,"audit unavailable"):
            create_appointment_in_db("Synthetic","+306900000000","00000000000",datetime.fromisoformat("2030-01-07T10:00:00+02:00"),actor_issuer="issuer",actor_subject="staff",correlation_id=uuid4())
        self.assertIs(connection.__exit__.call_args.args[0],RuntimeError)
