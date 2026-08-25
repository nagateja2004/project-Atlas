"""
Authentication and project authorization.

Until now `project_id` was data scoping, not authorization: any caller who knew
a project id could read and write it. This module supplies the missing half -
who the caller is, and whether they may touch the project they named.

Two deliberate choices:

1. **No new dependencies.** Password hashing uses `hashlib.scrypt` and tokens
   are HMAC-SHA256 signed, both from the standard library. `requirements.lock`
   is generated on Windows, so every added dependency risks the platform-
   specific breakage that already shipped once (`pywin32` pinned without an
   environment marker made the lock uninstallable on Linux). A security feature
   is the worst place to introduce that class of failure.

2. **Opaque signed tokens rather than JWT.** Nothing here needs a third party to
   validate a token, so the JWT header/algorithm negotiation - and the
   `alg: none` and algorithm-confusion footguns that come with it - buys nothing.
   The token is `base64url(payload) . base64url(hmac(secret, payload))`, verified
   with a constant-time compare and a fixed algorithm.

Enabling this is a config flip. See `Settings.auth_enabled` for why it does not
default to on yet.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid
from typing import Annotated, Literal

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from pydantic.functional_validators import AfterValidator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models import ProjectMember, User

logger = logging.getLogger("atlas.auth")

def _normalise_email(value: str) -> str:
    """
    Normalise and sanity-check an address without pulling in a dependency.

    pydantic's EmailStr needs the separate `email-validator` package. That was
    installed on the development machine but absent from requirements.lock, so
    importing this module succeeded locally and failed in CI - the same shape of
    fault as the unmarked pywin32 pin. Since these addresses are only ever
    compared against rows this application created, full RFC 5322 parsing buys
    nothing: what matters is that the value is trimmed, lowercased so lookups
    are stable, and obviously an address.
    """
    cleaned = value.strip().lower()
    local, _, domain = cleaned.partition("@")
    if not local or not domain or "." not in domain or any(c.isspace() for c in cleaned):
        raise ValueError("value is not a valid email address")
    return cleaned


Email = Annotated[str, AfterValidator(_normalise_email)]

Role = Literal["viewer", "reviewer", "admin"]

# Ordered by privilege so a requirement can be expressed as a floor rather than
# an exact match: a reviewer endpoint accepts an admin without listing them.
ROLE_ORDER: dict[str, int] = {"viewer": 0, "reviewer": 1, "admin": 2}

SCRYPT_N = 2**14          # ~16 MB per hash. Deliberate: see _hash_password.
SCRYPT_R = 8
SCRYPT_P = 1
SALT_BYTES = 16
KEY_BYTES = 32


# --------------------------------------------------------------------------- #
# passwords
# --------------------------------------------------------------------------- #

def hash_password(password: str) -> str:
    """
    Hash a password with scrypt.

    N is 2**14 rather than a larger value on purpose: scrypt is memory-hard and
    the deployment target is a 1 GB instance that already holds two transformer
    models. 2**14 costs roughly 16 MB and tens of milliseconds per verification,
    which is a real barrier to offline cracking without risking an OOM on the
    login path.
    """
    if not password:
        raise ValueError("password must not be empty")
    salt = secrets.token_bytes(SALT_BYTES)
    derived = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=KEY_BYTES
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(derived)}"


def verify_password(password: str, stored: str | None) -> bool:
    """
    Check a password against a stored hash.

    Returns False rather than raising on a malformed or absent hash: a user row
    with no usable credential must fail closed, and the caller should not be
    able to tell a bad password from a broken record.
    """
    if not password or not stored:
        return False
    try:
        scheme, n, r, p, salt_b64, key_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_unb64(salt_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(_unb64(key_b64)),
        )
    except (ValueError, TypeError):
        logger.warning("password_hash_unreadable")
        return False
    return hmac.compare_digest(derived, _unb64(key_b64))


# --------------------------------------------------------------------------- #
# tokens
# --------------------------------------------------------------------------- #

class TokenPayload(BaseModel):
    sub: str                 # user id
    email: str
    iat: int
    exp: int


def create_token(user: User, settings: Settings) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "iat": now,
        "exp": now + int(settings.auth_token_ttl_seconds),
    }
    body = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    return f"{body}.{_b64(_sign(body, _secret(settings)))}"


def decode_token(token: str, settings: Settings) -> TokenPayload | None:
    """
    Return the payload, or None for anything not currently valid.

    Every decode step sits inside the guard, including the signature. An earlier
    version verified the signature before the try block, so a token like
    "a.b.c" reached base64 decoding unprotected and raised binascii.Error -
    letting an unauthenticated caller turn a malformed header into a 500.
    """
    try:
        body, signature = token.split(".", 1)
        # Compare before parsing the payload: an unauthenticated caller must not
        # reach the JSON parser with attacker-controlled bytes.
        if not hmac.compare_digest(_sign(body, _secret(settings)), _unb64(signature)):
            return None
        payload = TokenPayload.model_validate_json(_unb64(body))
    except (ValueError, TypeError, binascii.Error):
        return None
    if payload.exp <= int(time.time()):
        return None
    return payload


def _sign(body: str, secret: bytes) -> bytes:
    return hmac.new(secret, body.encode("ascii"), hashlib.sha256).digest()


def _secret(settings: Settings) -> bytes:
    secret = settings.jwt_secret_key
    if not secret:
        # Refuse rather than fall back to a default. A predictable signing key
        # means anyone can mint a token for any user, which is worse than the
        # unauthenticated state this replaces.
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "JWT_SECRET_KEY is not configured; authentication cannot be used",
        )
    return secret.encode("utf-8")


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


# --------------------------------------------------------------------------- #
# request-time dependencies
# --------------------------------------------------------------------------- #

class Principal(BaseModel):
    """The authenticated caller, plus the role they hold on the project in hand."""

    user_id: uuid.UUID
    email: str
    role: Role = "viewer"
    authenticated: bool = True

    @property
    def is_anonymous(self) -> bool:
        return not self.authenticated


ANONYMOUS = Principal(
    user_id=uuid.UUID(int=0), email="anonymous", role="admin", authenticated=False
)

# auto_error=False so a missing header reaches our own handler, which can honour
# the auth_enabled flag instead of returning 403 unconditionally.
_bearer = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=1024)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserResponse"


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    is_active: bool
    memberships: list["MembershipResponse"] = Field(default_factory=list)


class MembershipResponse(BaseModel):
    project_id: uuid.UUID
    role: Role


LoginResponse.model_rebuild()
UserResponse.model_rebuild()


async def get_session_for_auth(request: Request) -> AsyncSession:
    async with request.app.state.session_factory() as session:
        yield session


async def current_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    """
    Resolve the caller.

    With authentication disabled this returns ANONYMOUS, which every
    authorization check treats as permitted - preserving today's behaviour
    exactly rather than half-enforcing it.
    """
    settings: Settings = request.app.state.settings
    if not settings.auth_enabled:
        return ANONYMOUS

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(credentials.credentials, settings)
    if payload is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    async with request.app.state.session_factory() as session:
        user = await session.get(User, uuid.UUID(payload.sub))
        if user is None or not user.is_active:
            # A deactivated user must lose access immediately, so the database
            # is consulted on every request rather than trusting the token
            # alone. These tokens are short-lived and cannot be revoked.
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User is not active")
        return Principal(user_id=user.id, email=user.email, role="viewer")


async def _role_on_project(
    session: AsyncSession, user_id: uuid.UUID, project_id: uuid.UUID
) -> str | None:
    return await session.scalar(
        select(ProjectMember.role).where(
            ProjectMember.user_id == user_id, ProjectMember.project_id == project_id
        )
    )


def require_project_role(minimum: Role = "viewer"):
    """
    Build a dependency asserting membership of the path's project at `minimum`.

    Absence of membership is reported as 404, not 403. A 403 confirms the
    project exists, which leaks the existence of other tenants' projects to
    anyone able to guess an id.
    """

    async def dependency(
        project_id: uuid.UUID,
        request: Request,
        principal: Principal = Depends(current_principal),
    ) -> Principal:
        settings: Settings = request.app.state.settings
        if not settings.auth_enabled:
            return ANONYMOUS

        async with request.app.state.session_factory() as session:
            role = await _role_on_project(session, principal.user_id, project_id)

        if role is None:
            logger.info(
                "authz_denied user=%s project=%s reason=not_a_member", principal.email, project_id
            )
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

        if ROLE_ORDER.get(role, -1) < ROLE_ORDER[minimum]:
            logger.info(
                "authz_denied user=%s project=%s role=%s required=%s",
                principal.email, project_id, role, minimum,
            )
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"This action requires the {minimum} role on the project",
            )

        return principal.model_copy(update={"role": role})

    return dependency


async def require_platform_admin(
    request: Request,
    principal: Principal = Depends(current_principal),
) -> Principal:
    """
    Gate user creation on holding admin somewhere.

    There is no platform-wide admin flag on `users`, so admin on any project is
    the available signal. It is intentionally coarse and is recorded in
    docs/LIMITATIONS.md rather than presented as tenant-safe.
    """
    settings: Settings = request.app.state.settings
    if not settings.auth_enabled:
        return ANONYMOUS

    async with request.app.state.session_factory() as session:
        roles = (
            await session.scalars(
                select(ProjectMember.role).where(ProjectMember.user_id == principal.user_id)
            )
        ).all()

    if "admin" not in set(roles):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator role required")
    return principal


async def enforce_project_access(
    request: Request,
    principal: Principal = Depends(current_principal),
) -> Principal:
    """
    Router-level guard for every project-scoped route.

    Deliberately reads `project_id` from `request.path_params` rather than
    declaring it as a parameter. Declaring it would make FastAPI demand the
    value as a query parameter on the collection routes (`GET /projects`,
    `POST /projects`), which have no such path segment. Reading the path also
    means this applies to routes added later without anyone remembering to
    annotate them - a forgotten annotation on a per-route guard is a silent
    hole, which is the failure mode worth designing out.

    The required role follows the method: reading needs `viewer`, anything that
    mutates needs `reviewer`. Membership management raises its own bar to
    `admin` separately.
    """
    settings: Settings = request.app.state.settings
    if not settings.auth_enabled:
        return ANONYMOUS

    raw_project_id = request.path_params.get("project_id")
    if raw_project_id is None:
        # A collection route. Authentication is still required - resolving the
        # principal above did that - but there is no project to authorize
        # against yet.
        return principal

    try:
        project_id = uuid.UUID(str(raw_project_id))
    except (ValueError, AttributeError):
        # Malformed id. Let the route's own validation produce the 422 rather
        # than reporting it as an authorization failure.
        return principal

    minimum: Role = "viewer" if request.method in {"GET", "HEAD", "OPTIONS"} else "reviewer"

    async with request.app.state.session_factory() as session:
        role = await _role_on_project(session, principal.user_id, project_id)

    if role is None:
        logger.info(
            "authz_denied user=%s project=%s reason=not_a_member", principal.email, project_id
        )
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    if ROLE_ORDER.get(role, -1) < ROLE_ORDER[minimum]:
        logger.info(
            "authz_denied user=%s project=%s role=%s required=%s method=%s",
            principal.email, project_id, role, minimum, request.method,
        )
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"This action requires the {minimum} role on the project",
        )

    return principal.model_copy(update={"role": role})
