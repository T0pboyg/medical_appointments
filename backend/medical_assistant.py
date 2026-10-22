import hashlib
import os
import threading
import time
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StringConstraints

from assistant_service import answer_question, AssistantBusy, AssistantUnavailable
from trusted_proxy import get_proxy_client_ip

router = APIRouter(prefix='/assistant', tags=['assistant'])
_attempts = {}
_rate_lock = threading.Lock()


def require_assistant_access(request: Request, client_ip: str = Depends(get_proxy_client_ip)):
    # Same origin only; no CORS and no reliance on staff authentication.
    if request.headers.get('origin') != os.getenv('ASSISTANT_ALLOWED_ORIGIN', 'http://localhost:5173'):
        raise HTTPException(403, 'Μη επιτρεπόμενη προέλευση αιτήματος.')
    now = time.monotonic()
    key = hashlib.sha256(client_ip.encode()).hexdigest()
    with _rate_lock:
        expired = [k for k, (start, _) in _attempts.items() if now - start >= 60]
        for k in expired:
            del _attempts[k]
        if key not in _attempts and len(_attempts) >= 1024:
            raise HTTPException(429, 'Η υπηρεσία είναι απασχολημένη.', headers={'Retry-After': '60'})
        start, count = _attempts.get(key, (now, 0))
        if count >= 6:
            raise HTTPException(429, 'Πολλά αιτήματα. Δοκιμάστε σε λίγο.', headers={'Retry-After': str(max(1, int(60 - (now-start))))})
        _attempts[key] = (start, count + 1)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1200)]
    consent: Literal[True]


@router.post('/chat', dependencies=[Depends(require_assistant_access)])
async def chat(body: ChatRequest):
    try:
        answer = await answer_question(body.message)
    except AssistantBusy:
        raise HTTPException(429, 'Ο Assistant εξυπηρετεί άλλη ερώτηση. Δοκιμάστε σε λίγο.', headers={'Retry-After': '5', 'Cache-Control': 'no-store'}) from None
    except AssistantUnavailable:
        raise HTTPException(503, 'Το τοπικό μοντέλο δεν είναι διαθέσιμο ή δεν έδωσε έγκυρη απάντηση. Δοκιμάστε αργότερα.', headers={'Cache-Control': 'no-store'}) from None
    return JSONResponse(answer, headers={'Cache-Control': 'no-store'})
