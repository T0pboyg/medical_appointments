import os

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Request
from fastapi import HTTPException
from authlib.integrations.base_client.errors import OAuthError

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
        raise ValueError("Ο issuer του Keycloak δεν συμφωνεί με τη ρύθμιση.")

    return metadata["issuer"]

@router.get("/login")
async def login(request: Request):
    await check_oidc_configuration()

    return await oauth.keycloak.authorize_redirect(
        request,
        os.environ["OIDC_REDIRECT_URI"],
        prompt="login"
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
            detail="Η σύνδεση απέτυχε. Ξεκίνα ξανά τη διαδικασία."
        ) from None

    user_info = token.get("userinfo")

    if not user_info or not user_info.get("sub"):
        request.session.clear()
        raise HTTPException(
            status_code=400,
            detail="Δεν επιβεβαιώθηκε η ταυτότητα του χρήστη."
        )

    roles = user_info.get("realm_roles", [])

    if not isinstance(roles, list) or "staff" not in roles:
        request.session.clear()
        raise HTTPException(
            status_code=403,
            detail="Δεν έχεις δικαίωμα πρόσβασης προσωπικού."
        )

    request.session.clear()

    return {"message": "Επιβεβαιώθηκε χρήστης με ρόλο προσωπικού."}