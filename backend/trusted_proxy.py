import ipaddress
import os
import secrets

from fastapi import HTTPException, Request


def get_proxy_client_ip(request: Request):
    expected_secret = os.environ["API_PROXY_SECRET"]
    received_secret = request.headers.get("x-api-proxy-secret", "")

    if not expected_secret or not secrets.compare_digest(
        expected_secret.encode("utf-8"),
        received_secret.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=403,
            detail="Μη επιτρεπόμενη διαδρομή πρόσβασης.",
        )

    forwarded_ip = request.headers.get("x-forwarded-for", "")

    try:
        address = ipaddress.ip_address(forwarded_ip)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Δεν προσδιορίστηκε έγκυρη IP επισκέπτη.",
        ) from None

    if isinstance(address, ipaddress.IPv6Address):
        address = address.ipv4_mapped or address

    return str(address)