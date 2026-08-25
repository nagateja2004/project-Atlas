"""
Authentication endpoints: sign in, identify yourself, manage accounts and access.

Kept out of app/api.py because that module is already large and because these
routes are the only ones that must remain reachable without a token.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    Email,
    LoginRequest,
    LoginResponse,
    MembershipResponse,
    Principal,
    Role,
    UserResponse,
    create_token,
    current_principal,
    hash_password,
    require_platform_admin,
    require_project_role,
    verify_password,
)
from app.models import Project, ProjectMember, User

logger = logging.getLogger("atlas.auth")

router = APIRouter(prefix="/auth", tags=["auth"])


async def get_session(request: Request):
    async with request.app.state.session_factory() as session:
        yield session


async def _memberships(session: AsyncSession, user_id: uuid.UUID) -> list[MembershipResponse]:
    rows = (
        await session.execute(
            select(ProjectMember.project_id, ProjectMember.role).where(
                ProjectMember.user_id == user_id
            )
        )
    ).all()
    return [MembershipResponse(project_id=project_id, role=role) for project_id, role in rows]


async def _user_response(session: AsyncSession, user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        memberships=await _memberships(session, user.id),
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> LoginResponse:
    settings = request.app.state.settings
    email = payload.email.strip().lower()
    user = await session.scalar(select(User).where(User.email == email))

    # One message and one code for every failure mode - unknown address, wrong
    # password, deactivated account, or an account with no credential set. A
    # distinguishable response turns this endpoint into a user-enumeration
    # oracle. The password is still verified against a dummy hash when the user
    # is missing so the timing does not answer the question either.
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        if user is None:
            verify_password(payload.password, _DUMMY_HASH)
        logger.info("login_failed email=%s", email)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    logger.info("login_ok user=%s", user.email)
    return LoginResponse(
        access_token=create_token(user, settings),
        expires_in=int(settings.auth_token_ttl_seconds),
        user=await _user_response(session, user),
    )


# Fixed cost comparison for the unknown-user path. Generated once at import so a
# login attempt for a missing address does the same scrypt work as a real one.
_DUMMY_HASH = hash_password("not-a-real-password")


@router.get("/me", response_model=UserResponse)
async def me(
    request: Request,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    if principal.is_anonymous:
        # Authentication is disabled. Say so plainly instead of inventing a
        # user, so a caller can tell the difference.
        return UserResponse(
            id=principal.user_id, email="anonymous (authentication disabled)", is_active=True
        )
    user = await session.get(User, principal.user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")
    return await _user_response(session, user)


class UserCreate(BaseModel):
    email: Email
    password: str = Field(min_length=12, max_length=1024)
    # Optional first grant, so bootstrapping an account and its access is one call.
    project_id: uuid.UUID | None = None
    role: Role = "viewer"


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    session: AsyncSession = Depends(get_session),
    _: Principal = Depends(require_platform_admin),
) -> UserResponse:
    email = payload.email.strip().lower()
    if await session.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with that email already exists")

    user = User(email=email, password_hash=hash_password(payload.password), is_active=True)
    session.add(user)
    await session.flush()

    if payload.project_id is not None:
        if not await session.get(Project, payload.project_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
        session.add(
            ProjectMember(project_id=payload.project_id, user_id=user.id, role=payload.role)
        )

    await session.commit()
    await session.refresh(user)
    logger.info("user_created email=%s", user.email)
    return await _user_response(session, user)


class MemberCreate(BaseModel):
    email: Email
    role: Role = "viewer"


member_router = APIRouter(prefix="/projects", tags=["auth"])


@member_router.post(
    "/{project_id}/members",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    project_id: uuid.UUID,
    payload: MemberCreate,
    session: AsyncSession = Depends(get_session),
    _: Principal = Depends(require_project_role("admin")),
) -> MembershipResponse:
    """Grant an existing account a role on this project. Requires admin here."""
    email = payload.email.strip().lower()
    user = await session.scalar(select(User).where(User.email == email))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No user with that email")

    existing = await session.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user.id
        )
    )
    if existing is not None:
        existing.role = payload.role
    else:
        session.add(ProjectMember(project_id=project_id, user_id=user.id, role=payload.role))
    await session.commit()
    logger.info("member_granted project=%s email=%s role=%s", project_id, email, payload.role)
    return MembershipResponse(project_id=project_id, role=payload.role)


@member_router.get("/{project_id}/members", response_model=list[MembershipResponse])
async def list_members(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _: Principal = Depends(require_project_role("admin")),
) -> list[MembershipResponse]:
    rows = (
        await session.execute(
            select(ProjectMember.project_id, ProjectMember.role).where(
                ProjectMember.project_id == project_id
            )
        )
    ).all()
    return [MembershipResponse(project_id=pid, role=role) for pid, role in rows]
