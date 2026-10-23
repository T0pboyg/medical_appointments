# Expand verified assistant sources and Greek questions

User delegates topic/source selection and authorizes direct edits. Extend the existing curated-source architecture; no free-form medical generation, training, new dependency or appointment-form change.

- [x] Verify original NHS cold/dizziness/stroke, MedlinePlus healthy sleep, and CDC antibiotic-use pages; preserve adaptation attribution and prototype clinical-review status.
- [x] Add synthetic regression questions before implementation, covering natural Greek phrasing, source relevance, urgent priority, child/pregnancy boundaries, and medication refusal.
- [x] Extend explicit retrieval rules and curated content for cold/nasal symptoms, dizziness, sleep habits, and general antibiotic education.
- [x] Use topic-specific friendly introductions, exact social-message replies, and a useful unknown-topic fallback; keep emergency wording and source verification separate from the LLM.
- [x] Run the full backend suite, production frontend build and live local-model examples; document limitations and results.

Review focus: avoid implying a cold diagnosis from nasal symptoms; never suppress emergency symptoms behind greetings or booking intent; distinguish generic antibiotic information from personal dosing; keep all model IDs inside retrieved candidates; never claim an official Greek translation or clinical approval.

Verification: 110 backend tests passed; Vite production build passed; real Ollama examples for sleep, antibiotics and visit preparation returned grounded responses with correct source IDs (4.9s, 0.8s and 0.5s in this run). No commit or push.
