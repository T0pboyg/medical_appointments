# Assistant warmth and live availability

Approved design: recognize natural Greek headache expressions, separate fever from sore throat, add brief empathy without changing medical warnings, and answer next-week availability from the existing booking rules. No booking or patient-data access through chat.

Implementation uses the writing-plans and TDD workflows, executed inline under the user's existing approval.

- [x] Add regression tests for fever/headache, duration acknowledgement, and source relevance.
- [x] Extract the existing slot calculation into `backend/availability_service.py`, preserving the public endpoint's mocked reader interfaces.
- [x] Add `backend/assistant_booking.py`: bounded date resolution, exact date range, at most six example slots, no reservation, no LLM-generated availability. Ambiguous dates require clarification. Database failures must not look like an empty calendar.
- [x] Integrate booking lookup off the async event loop, after symptom routing. Make preparation and booking introductions warmer.
- [x] Run assistant tests, full backend suite, frontend build, and whitespace checks. Document date support and limitations in `AI_ASSISTANT.md`.

Review focus: week rollover and Athens timezone; partial block overlaps; empty calendar versus lookup failure; symptom priority over booking; ambiguous dates and mixed date constraints must not produce misleading hours.

Verification: 99 backend tests passed; Vite production build passed; live assistant lookup returned actual slots; HTTP proxy returned 200 with Cache-Control no-store. No commit or push.
