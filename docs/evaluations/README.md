# Public assistant evaluation — 25 October 2026

Synthetic questions only; no real patient data and no appointment writes.

The initial and final JSON reports preserve all 30 questions and responses.
The final report records 30/30 expected routes and basic boundary checks with
real local Ollama. This is not a clinical assessment, diagnosis benchmark,
general language-understanding score or proof of safety on unseen questions.

Changes prompted by this run:

- Recognize visit description/note-taking questions, backed by MedlinePlus.
- Give existing lab preparation warnings about not stopping medicines without
  clinician instructions, instead of a generic unknown response. Medication
  selection, dosing, personal numeric interpretation and therapy changes
  remain outside scope.
- Explain reference ranges without interpreting a patient's values.
- Include visit note-taking evidence when explicitly asked in a symptom query,
  retaining emergency priority and adult/special-population boundaries.
- Recognize free-slot questions without the word appointment.
- Explain that the user completes the booking form; protect national ID and
  phone information with a direct privacy response.

Authoritative sources rechecked for the updates:

- https://medlineplus.gov/talkingwithyourdoctor.html
- https://medlineplus.gov/lab-tests/how-to-prepare-for-a-lab-test/
- https://medlineplus.gov/lab-tests/how-to-understand-your-lab-results/

Permanent synthetic cases: `backend/tests/fixtures/public_assistant_questions.json`.
Mocked regression test: `backend/tests/test_assistant_evaluation.py`.
The mock isolates routing/guard checks; it does not evaluate model selection.

Repeat the live evaluation from the repository with Ollama/backend running:

```powershell
docker compose exec backend python tests/evaluate_public_assistant.py --output /app/assistant-evaluation.json
```

The output is `backend/assistant-evaluation.json` on the host. It may contain
live public availability times. Never substitute real patient details in the
question set. The evaluator calls the service directly, so it does not test
HTTP Origin checks, rate limits or the browser. Those remain separate tests.
