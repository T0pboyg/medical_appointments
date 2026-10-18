import os
import secrets
import httpx

from access_control import is_active_staff
from sessions import delete_staff_sessions_for_user

from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import RedirectResponse
from sessions import (
    create_staff_session,
    delete_session,
    get_staff_session,
)
from fastapi import Depends
from starlette.responses import JSONResponse


router = APIRouter(prefix="/auth")

oauth = OAuth()

oauth.register(
    name="keycloak",
    client_id=os.environ["OIDC_CLIENT_ID"],
    client_secret=os.environ["OIDC_CLIENT_SECRET"],
    server_metadata_url=os.environ["OIDC_METADATA_URL"],
    client_kwargs={
        "scope": "openid profile",
        "code_challenge_method": "S256",
    },
)


async def check_oidc_configuration():
    metadata = await oauth.keycloak.load_server_metadata()

    if metadata["issuer"] != os.environ["OIDC_ISSUER"]:
        raise ValueError(
            "Ο issuer του Keycloak δεν συμφωνεί με τη ρύθμιση."
        )

    return metadata["issuer"]


@router.get("/login")
async def login(request: Request):
    await check_oidc_configuration()

    return await oauth.keycloak.authorize_redirect(
        request,
        os.environ["OIDC_REDIRECT_URI"],
        prompt="login",
    )


@router.get("/callback")
async def callback(request: Request):
    await check_oidc_configuration()

    try:
        token = await oauth.keycloak.authorize_access_token(request)
    except OAuthError:
        request.session.clear()
        raise HTTPException(
            status_code=400,
            detail="Η σύνδεση απέτυχε. Ξεκίνα ξανά τη διαδικασία.",
        ) from None

    user_info = token.get("userinfo")

    if not user_info or not user_info.get("sub"):
        request.session.clear()
        raise HTTPException(
            status_code=400,
            detail="Δεν επιβεβαιώθηκε η ταυτότητα του χρήστη.",
        )

    roles = user_info.get("realm_roles", [])

    if not isinstance(roles, list) or "staff" not in roles:
        request.session.clear()
        raise HTTPException(
            status_code=403,
            detail="Δεν έχεις δικαίωμα πρόσβασης προσωπικού.",
        )

    previous_session_id = request.cookies.get("staff_session")

    if previous_session_id:
        await run_in_threadpool(
            delete_session,
            previous_session_id,
        )

    session_id = await run_in_threadpool(
        create_staff_session,
        user_info["iss"],
        user_info["sub"],
    )

    request.session.clear()

    response = RedirectResponse(
        url="http://localhost:5173/admin",
        status_code=303,
    )

    response.set_cookie(
        key="staff_session",
        value=session_id,
        max_age=8 * 60 * 60,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )

    return response

async def require_staff(request: Request):
    session_id = request.cookies.get("staff_session")

    session = await run_in_threadpool(
        get_staff_session,
        session_id,
    )

    if session is None:
        raise HTTPException(
            status_code=401,
            detail="Απαιτείται σύνδεση προσωπικού.",
        )

    issuer = session.get("issuer")
    subject = session.get("subject")

    if (
        issuer != os.environ["OIDC_ISSUER"]
        or not isinstance(subject, str)
        or not subject
    ):
        raise HTTPException(
            status_code=401,
            detail="Η συνεδρία δεν είναι έγκυρη.",
        )

    try:
        allowed = await is_active_staff(subject)
    except httpx.HTTPError:
        raise HTTPException(
            status_code=503,
            detail="Δεν είναι διαθέσιμος ο έλεγχος πρόσβασης. Δοκίμασε αργότερα.",
        ) from None

    if not allowed:
        await run_in_threadpool(
            delete_staff_sessions_for_user,
            issuer,
            subject,
        )

        raise HTTPException(
            status_code=401,
            detail="Η πρόσβαση προσωπικού έχει ανακληθεί.",
        )

    return session


@router.get("/csrf")
async def get_csrf_token(session: dict = Depends(require_staff)):
    csrf_token = session.get("csrf_token")

    if not csrf_token:
        raise HTTPException(
            status_code=401,
            detail="Χρειάζεται νέα σύνδεση προσωπικού.",
        )

    return JSONResponse(
        {"csrf_token": csrf_token},
        headers={"Cache-Control": "no-store"},
    )

async def require_staff_change(
    request: Request,
    session: dict = Depends(require_staff),
):
    if request.headers.get("origin") != "http://localhost:5173":
        raise HTTPException(
            status_code=403,
            detail="Μη επιτρεπόμενη προέλευση αιτήματος.",
        )

    expected_token = session.get("csrf_token")
    received_token = request.headers.get("x-csrf-token")

    if (
        not isinstance(expected_token, str)
        or not received_token
        or not secrets.compare_digest(expected_token, received_token)
    ):
        raise HTTPException(
            status_code=403,
            detail="Μη έγκυρο CSRF token.",
        )

    return session


@router.post("/logout")
async def logout(
    request: Request,
    session: dict = Depends(require_staff_change),
):
    session_id = request.cookies.get("staff_session")

    await run_in_threadpool(delete_session, session_id)

    response = JSONResponse(
        {"message": "Η αποσύνδεση ολοκληρώθηκε."},
        headers={"Cache-Control": "no-store"},
    )

    response.delete_cookie("staff_session", path="/")

    return response