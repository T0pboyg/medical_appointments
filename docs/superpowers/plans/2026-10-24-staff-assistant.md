# Staff assistant implementation

User authorizes direct file changes. Extend the existing local Ollama integration with a separate staff-only assistant. First supported tasks: list appointments on one date, list free slots on one date, and preview/confirm cancellation of one appointment. No bulk actions, medication advice, arbitrary SQL, appointment creation or rescheduling.

Architecture: constrained LLM intent/name extraction from the command only; deterministic server date resolution; bounded SQL reads of id/name/start only; signed five-minute cancellation previews bound to the authenticated staff session. Confirmation rechecks live staff authorization, Origin and CSRF. The existing cancellation transaction records the actor and audit event and additionally guards the previewed appointment snapshot. The model never receives appointment records or controls writes.

- [x] Add failing tests for date ambiguity, LLM validation, staff/CSRF boundaries, preview-only behavior, signed session binding, expiry/tampering, multiple matches and stale previews.
- [x] Implement scoped parser, minimal database reads, cancellation snapshot guard and staff API.
- [x] Add a staff-only chat panel, candidate cards and explicit confirm button; clear transient state on close/session loss. Update the admin list after cancellation.
- [x] Run full backend tests, frontend build and a live local-model parsing smoke test. Document supported commands and limitations.

Review focus: wrong patient/date interpretation; stale appointment between preview and confirmation; expired/revoked session; bulk or injected instructions; accidental patient-data exposure to the public assistant or model. Tests use synthetic records only.

Independent review: three findings addressed in one fix pass. Date constraints (mixed full/partial dates, unsupported week offsets and named-month ID constraints) now require clarification; unsupported time constraints are rejected before reads. The bulk guard applies only to cancellations. Closing is disabled during confirmation and stale JSON responses are ignored after closing other requests. Regression tests reproduced date/bulk issues before fixes. Integration tests require the migration role against appointments_migration_test, not the restricted application role.

Final verification: 124 backend tests passed on the isolated migration-test database; Vite production build passed; real local Ollama recognized four synthetic list/availability/cancel-name/cancel-ID commands. No live appointment was cancelled. No commit or push. Browser interaction remains for the user to verify.
