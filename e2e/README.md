# Isolated browser journey tests

```powershell
docker compose -f compose.e2e.yaml up --build --abort-on-container-exit --exit-code-from runner
docker compose -f compose.e2e.yaml down --remove-orphans
```

Uses the separate Compose project `medical-appointments-e2e`. No host ports,
production volumes, real `.env` values, real Keycloak accounts or Ollama are
used. PostgreSQL stores synthetic data in tmpfs. The normal application stack
can remain running. The first run downloads the pinned Playwright browser
image; subsequent runs reuse it. Local test artifacts are ignored by Git.

Coverage:

- Fill the real form and create an appointment through Vite -> FastAPI -> PostgreSQL.
- Verify the booked slot disappears from public availability.
- Load the appointment in the real Admin component and cancel through its confirmation dialog.
- Verify one database audit event and that the slot is free again.
- Backdate a retained staff session beyond the 15-minute idle limit and verify patient cards are cleared.
- Simulate a failed booking network request and verify an error, no success message and a usable retry button.

The test entrypoint `backend/tests/e2e_server.py` is mounted only into the
isolated backend and refuses to start without the explicit test-mode marker
and database name `appointments_e2e`. Production `main.py` never imports it.
It applies the real migrations and creates real staff sessions, but simulates
the external staff-role response. Login is test-only: this does **not** test
the real Keycloak/OIDC/TOTP login screen. CSRF, session lookup, application
permissions, booking rules, cancellation transaction and audit remain active.

The browser runner shares only the test frontend's network namespace so that
the app retains its real `http://localhost:5173` Origin checks. Production
security settings are not relaxed for tests. Playwright and the image are
both pinned to 1.64.0 in the separate test package and lockfile; application
dependencies remain unchanged.

GitHub runs the same command through `browser-tests.yml`. Failure screenshots
and traces contain only synthetic data and are retained for seven days.
