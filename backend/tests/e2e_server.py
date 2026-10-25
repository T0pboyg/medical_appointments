"""Isolated browser-test entrypoint. Never imported by production main.py."""
import os

if __name__ == '__main__':
    if os.environ.get('E2E_TEST_MODE') != 'isolated-e2e-only':
        raise RuntimeError('E2E entrypoint requires isolated test mode')
    import psycopg
    from psycopg.conninfo import conninfo_to_dict
    if conninfo_to_dict(os.environ['DATABASE_URL']).get('dbname') != 'appointments_e2e':
        raise RuntimeError('E2E entrypoint refuses non-test databases')

    from migrate import apply_migrations
    with psycopg.connect(os.environ['DATABASE_URL']) as connection:
        if connection.execute('SELECT current_database()').fetchone()[0] != 'appointments_e2e':
            raise RuntimeError('Wrong database')
        apply_migrations(connection)

    import auth
    import hashlib
    import uvicorn
    from fastapi import Depends, HTTPException, Request
    from fastapi.responses import JSONResponse
    from main import app
    from sessions import create_staff_session
    from trusted_proxy import get_proxy_client_ip

    async def test_staff_role(subject):
        return subject == 'e2e-staff'
    auth.is_active_staff = test_staff_role

    @app.get('/__e2e/health')
    def health():
        return {'test_environment': True}

    @app.post('/__e2e/login', dependencies=[Depends(get_proxy_client_ip)])
    def login(request: Request):
        if request.headers.get('origin') != 'http://localhost:5173':
            raise HTTPException(403)
        token = create_staff_session(os.environ['OIDC_ISSUER'], 'e2e-staff')
        response = JSONResponse({'test_login': True}, headers={'Cache-Control': 'no-store'})
        response.set_cookie('staff_session', token, httponly=True, samesite='lax')
        return response

    @app.post('/__e2e/expire', dependencies=[Depends(auth.require_staff_change)])
    def expire(request: Request):
        session_hash = hashlib.sha256(request.cookies['staff_session'].encode()).hexdigest()
        with psycopg.connect(os.environ['DATABASE_URL']) as connection:
            retained = connection.execute(
                "UPDATE staff_sessions SET last_seen_at = CURRENT_TIMESTAMP - INTERVAL '16 minutes' WHERE session_hash = %s RETURNING session_hash",
                (session_hash,),
            ).fetchone() is not None
        return JSONResponse({'expired': True, 'session_retained': retained}, headers={'Cache-Control': 'no-store'})

    @app.get('/__e2e/audit/{appointment_id}', dependencies=[Depends(auth.require_staff), Depends(get_proxy_client_ip)])
    def audit(appointment_id: int):
        with psycopg.connect(os.environ['DATABASE_URL']) as connection:
            count = connection.execute("SELECT count(*) FROM audit_events WHERE appointment_id = %s AND action = 'appointment.cancelled'", (appointment_id,)).fetchone()[0]
        return JSONResponse({'cancellations': count}, headers={'Cache-Control': 'no-store'})

    uvicorn.run(app, host='0.0.0.0', port=8000, access_log=False)
