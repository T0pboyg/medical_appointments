# Shared booking calendar implementation plan

**Goal:** Replace rescheduling date typing with the same calendar used by public booking.

**Approved approach:** User requested direct implementation of the shared-component approach proposed in chat. Keep existing availability requests, confirmation, CSRF and transaction checks. Do not change the admin counts calendar or pending history work.

**Files:** Create frontend/BookingCalendar.jsx; integrate in frontend/main.jsx and RescheduleAppointment.jsx; scope rescheduling styles in Admin.css; extend existing isolated browser tests.

- [x] Add failing browser coverage for selecting a reschedule day in both the main card and assistant dialog, disabled past/weekend dates and clearing old times.
- [x] Extract public calendar rendering into a controlled selectedDate/onSelectDate component with its own visible month, UTC grid arithmetic and Athens today boundary; no duplicate element IDs.
- [x] Reuse for rescheduling with busy/conflict disabling and date-selection feedback. Retain existing slot loading and audited submission.
- [x] Run static browser suite, fix regressions and rebuild local static frontend. Clean test containers; no commit or push.

**Verification:** 17 static browser tests passed, including a browser in Honolulu while Athens is on the following date. Same-day reselect regression was reproduced and fixed; it now preserves the selected time. Independent read-only review found no blocking issues. No backend or schema changes in this task.

**Validation:** Existing public booking/cancellation journey; existing assistant move tests; new date selection tests. Browser tests must use only isolated/synthetic records. Existing history/schema/permissions edits are preserved.
