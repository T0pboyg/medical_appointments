# Isolated browser journey

User approved committing the public-assistant evaluation and proceeding with
browser-level booking/admin/cancellation tests. Public-assistant changes were
committed as 1c9dc62; no push was requested.

- [x] Create a separate Compose project with tmpfs PostgreSQL, real migrations,
  real frontend/backend, no published ports or production volumes.
- [x] Add a guarded test-only entrypoint: refuses a normal database and never
  registers hooks in production main.py. Simulate external role lookup only;
  retain real sessions, CSRF, booking rules and audited cancellation.
- [x] Pin Playwright package/browser image together, separate from app dependencies.
- [x] Exercise form booking, admin lookup, confirmation, audit count and freed slot.
- [x] Exercise expired idle session and failed booking network request.
- [x] Add CI workflow, ignored synthetic artifacts and repeatable instructions.
- [x] Verify 3 browser scenarios and 138 backend tests.

Independent review: production/isolation and CI exit wiring passed static review.
Reviewer found the initial expiry hook deleted the session rather than testing
timestamp expiry. A regression requirement reproduced this; the hook now keeps
the row and backdates last_seen_at beyond 15 minutes. All final checks passed.

Ruling: browser authentication uses an isolated stub for the external staff-role
response, so these tests do not validate Keycloak/OIDC/TOTP. They exercise real
application/session/database behavior; a separate real identity-provider suite
would be required for that coverage. This limitation is documented in e2e/README.md.
