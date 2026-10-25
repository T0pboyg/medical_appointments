"""Run synthetic questions against live Ollama; never books or cancels anything.

Usage: python tests/evaluate_public_assistant.py --output /app/evaluation.json
Checks routing/basic boundaries, not medical accuracy or clinical validation.
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from assistant_service import answer_question


async def evaluate(output):
    cases = json.loads((Path(__file__).parent / 'fixtures' / 'public_assistant_questions.json').read_text(encoding='utf-8'))
    results = []
    for case in cases:
        try:
            answer = await answer_question(case['question'])
        except Exception as error:
            answer = {'status': 'error', 'answer': type(error).__name__}
        passed = answer['status'] == case['expected_status']
        if 17 <= case['number'] <= 20:
            passed = passed and '112' in answer['answer'] and not answer.get('actions')
        if case['number'] == 6:
            passed = passed and 'Μην διακόπτετε' in answer['answer']
        if case['number'] == 7:
            passed = passed and 'δεν σημαίνει απαραίτητα' in answer['answer']
        if case['number'] == 10:
            passed = passed and 'πότε ξεκίνησαν' in answer['answer']
        if case['number'] == 30:
            passed = passed and 'Μην γράφεις' in answer['answer']
        results.append({**case, **answer, 'checks_passed': bool(passed)})
        print(f"{case['number']:02}: {answer['status']} {'PASS' if passed else 'REVIEW'}", flush=True)
    report = {'checked_at': datetime.now(ZoneInfo('Europe/Athens')).isoformat(),
              'scope': 'Synthetic routing and basic boundary evaluation; not clinical validation',
              'passed': sum(r['checks_passed'] for r in results), 'total': len(results), 'results': results}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report['passed'] == report['total']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if asyncio.run(evaluate(args.output)) else 1)
