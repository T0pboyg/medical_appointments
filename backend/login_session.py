from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

from sessions import (
    create_session,
    delete_session,
    get_session,
    update_session,
)


class LoginSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if not request.url.path.startswith("/auth/"):
            return await call_next(request)

        cookie_name = "oidc_login_session"
        session_id = request.cookies.get(cookie_name)

        stored_data = None
        if session_id:
            stored_data = await run_in_threadpool(
                get_session, session_id
            )

        if stored_data is None:
            session_id = None

        request.scope["session"] = (
            stored_data if stored_data is not None else {}
        )

        response = await call_next(request)
        session_data = request.scope["session"]

        if session_data:
            if session_id:
                updated = await run_in_threadpool(
                    update_session, session_id, session_data
                )

                if not updated:
                    response.delete_cookie(cookie_name, path="/")
            else:
                session_id = await run_in_threadpool(
                    create_session, session_data
                )

                response.set_cookie(
                    key=cookie_name,
                    value=session_id,
                    max_age=600,
                    httponly=True,
                    samesite="lax",
                    secure=False,
                    path="/",
                )
        else:
            if session_id:
                await run_in_threadpool(delete_session, session_id)

            if cookie_name in request.cookies:
                response.delete_cookie(cookie_name, path="/")

        return response