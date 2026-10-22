"""Supabase Auth JWT verification.

Supabase issues a JWT for every session, including anonymous sign-ins (`is_anonymous: true`).
The API trusts only the token's signature, issuer, audience and expiry; never the request body.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings

ASYMMETRIC_ALGORITHMS = ["ES256", "RS256", "EdDSA"]


@dataclass(frozen=True, slots=True)
class CurrentUser:
    id: UUID
    is_anonymous: bool


class InvalidToken(Exception):
    pass


class JwtVerifier:
    def __init__(self, settings: Settings) -> None:
        self._audience = settings.jwt_audience
        self._issuer = settings.jwt_issuer
        self._secret = (
            settings.supabase_jwt_secret.get_secret_value() if settings.supabase_jwt_secret else None
        )
        # PyJWKClient caches keys and refetches when it sees an unknown `kid` (key rotation).
        self._jwks = None if self._secret else jwt.PyJWKClient(settings.jwks_url, cache_keys=True)

    async def verify(self, token: str) -> CurrentUser:
        try:
            if self._secret:
                key: Any = self._secret
                algorithms = ["HS256"]
            elif self._jwks is None:
                raise InvalidToken("No JWT verification key configured.")
            else:
                key = (await run_in_threadpool(self._jwks.get_signing_key_from_jwt, token)).key
                algorithms = ASYMMETRIC_ALGORITHMS
            claims = jwt.decode(
                token,
                key,
                algorithms=algorithms,
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["sub", "exp", "aud", "iss"]},
            )
            return CurrentUser(id=UUID(claims["sub"]), is_anonymous=bool(claims.get("is_anonymous", False)))
        except (jwt.PyJWTError, ValueError) as exc:
            raise InvalidToken(str(exc)) from exc


_bearer = HTTPBearer(auto_error=False)


def get_verifier(request: Request) -> JwtVerifier:
    verifier: JwtVerifier = request.app.state.verifier
    return verifier


async def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    verifier: JwtVerifier = Depends(get_verifier),
) -> CurrentUser:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail="Sign-in required.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if creds is None:
        raise unauthorized
    try:
        return await verifier.verify(creds.credentials)
    except InvalidToken:
        raise unauthorized from None
