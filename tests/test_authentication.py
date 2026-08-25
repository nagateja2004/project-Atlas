"""
Authentication and project authorization.

The behaviour worth protecting here is not "login works" - it is that the guard
cannot be bypassed, that a non-member cannot learn a project exists, and that
turning the feature off restores the previous behaviour exactly.
"""

import asyncio
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth import (
    create_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.config import Settings
from app.main import app
from app.models import Base, ProjectMember, User

SECRET = "test-signing-secret-not-a-real-key"
PASSWORD = "correct horse battery staple"


def _settings(**overrides) -> Settings:
    base = {
        "auth_enabled": True,
        "jwt_secret_key": SECRET,
        "embedding_backend": "local_hash",
    }
    base.update(overrides)
    return Settings(**base)


@pytest.fixture()
def engine(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'auth.db'}")

    async def create_schema() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(create_schema())
    yield engine
    asyncio.run(engine.dispose())


def _seed(session_factory, *, email: str, role: str | None, project_id, active: bool = True):
    """Create a user and optionally grant a role on a project. Returns the user id."""

    async def run():
        async with session_factory() as session:
            user = User(email=email, password_hash=hash_password(PASSWORD), is_active=active)
            session.add(user)
            await session.flush()
            if role is not None:
                session.add(
                    ProjectMember(project_id=project_id, user_id=user.id, role=role)
                )
            await session.commit()
            return user.id

    return asyncio.run(run())


# --------------------------------------------------------------------------- #
# passwords
# --------------------------------------------------------------------------- #

def test_password_round_trip_and_rejects_wrong_password() -> None:
    stored = hash_password(PASSWORD)
    assert stored.startswith("scrypt$")
    assert PASSWORD not in stored
    assert verify_password(PASSWORD, stored)
    assert not verify_password("wrong password entirely", stored)


def test_password_hash_is_salted_so_equal_passwords_differ() -> None:
    assert hash_password(PASSWORD) != hash_password(PASSWORD)


@pytest.mark.parametrize("stored", [None, "", "notascheme$1$2$3$4$5", "scrypt$bad", "plaintext"])
def test_unusable_hash_fails_closed(stored) -> None:
    assert not verify_password(PASSWORD, stored)


def test_empty_password_is_refused_at_hash_time() -> None:
    with pytest.raises(ValueError):
        hash_password("")


# --------------------------------------------------------------------------- #
# tokens
# --------------------------------------------------------------------------- #

def _user() -> User:
    return User(id=uuid.uuid4(), email="token@example.com", password_hash="x", is_active=True)


def test_token_round_trip() -> None:
    settings = _settings()
    user = _user()
    payload = decode_token(create_token(user, settings), settings)
    assert payload is not None
    assert payload.sub == str(user.id)
    assert payload.email == user.email


def test_tampered_payload_is_rejected() -> None:
    settings = _settings()
    body, signature = create_token(_user(), settings).split(".", 1)
    forged = f"{body[:-2]}XY.{signature}"
    assert decode_token(forged, settings) is None


def test_token_signed_with_another_secret_is_rejected() -> None:
    token = create_token(_user(), _settings(jwt_secret_key="a-different-secret"))
    assert decode_token(token, _settings()) is None


def test_expired_token_is_rejected() -> None:
    settings = _settings(auth_token_ttl_seconds=1)
    token = create_token(_user(), settings)
    assert decode_token(token, settings) is not None
    # Rather than sleeping, re-decode against a clock the token is already
    # behind by shrinking the window it was minted with.
    time.sleep(1.1)
    assert decode_token(token, settings) is None


@pytest.mark.parametrize("token", ["", "no-dot", "a.b.c", "....", "onlybody."])
def test_malformed_tokens_are_rejected_without_raising(token) -> None:
    assert decode_token(token, _settings()) is None


# --------------------------------------------------------------------------- #
# the guard
# --------------------------------------------------------------------------- #

def test_disabled_auth_leaves_behaviour_unchanged(engine) -> None:
    """The flag must be a true no-op, not a partial enforcement."""
    with TestClient(app) as client:
        app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
        app.state.settings = _settings(auth_enabled=False)

        created = client.post("/projects", json={"name": "Anonymous access"})
        assert created.status_code == 201
        project_id = created.json()["id"]

        assert client.get(f"/projects/{project_id}/documents").status_code == 200
        assert client.get("/auth/me").json()["email"].startswith("anonymous")


def test_enabled_auth_rejects_calls_without_a_token(engine) -> None:
    with TestClient(app) as client:
        app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
        app.state.settings = _settings(auth_enabled=False)
        project_id = client.post("/projects", json={"name": "Guarded"}).json()["id"]

        app.state.settings = _settings(auth_enabled=True)
        response = client.get(f"/projects/{project_id}/documents")
        assert response.status_code == 401
        assert response.headers.get("www-authenticate") == "Bearer"


def test_login_then_access_as_member(engine) -> None:
    with TestClient(app) as client:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        app.state.session_factory = session_factory
        app.state.settings = _settings(auth_enabled=False)
        project_id = client.post("/projects", json={"name": "Member access"}).json()["id"]
        _seed(session_factory, email="member@example.com", role="reviewer",
              project_id=uuid.UUID(project_id))

        app.state.settings = _settings(auth_enabled=True)
        login = client.post(
            "/auth/login", json={"email": "member@example.com", "password": PASSWORD}
        )
        assert login.status_code == 200, login.text
        body = login.json()
        assert body["token_type"] == "bearer"
        assert body["user"]["memberships"][0]["role"] == "reviewer"

        headers = {"Authorization": f"Bearer {body['access_token']}"}
        assert client.get(f"/projects/{project_id}/documents", headers=headers).status_code == 200

        me = client.get("/auth/me", headers=headers).json()
        assert me["email"] == "member@example.com"


def test_non_member_gets_404_not_403(engine) -> None:
    """
    A 403 would confirm the project exists. For someone who is not a member,
    the project must be indistinguishable from one that was never created.
    """
    with TestClient(app) as client:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        app.state.session_factory = session_factory
        app.state.settings = _settings(auth_enabled=False)
        theirs = client.post("/projects", json={"name": "Someone else"}).json()["id"]
        mine = client.post("/projects", json={"name": "Mine"}).json()["id"]
        _seed(session_factory, email="outsider@example.com", role="admin",
              project_id=uuid.UUID(mine))

        app.state.settings = _settings(auth_enabled=True)
        token = client.post(
            "/auth/login", json={"email": "outsider@example.com", "password": PASSWORD}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        assert client.get(f"/projects/{mine}/documents", headers=headers).status_code == 200

        denied = client.get(f"/projects/{theirs}/documents", headers=headers)
        assert denied.status_code == 404
        assert "not found" in denied.json()["error"]["message"].lower()

        # A non-existent project must look identical to one they cannot see.
        unknown = client.get(f"/projects/{uuid.uuid4()}/documents", headers=headers)
        assert unknown.status_code == denied.status_code


def test_viewer_cannot_mutate_but_reviewer_can(engine) -> None:
    with TestClient(app) as client:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        app.state.session_factory = session_factory
        app.state.settings = _settings(auth_enabled=False)
        project_id = client.post("/projects", json={"name": "Roles"}).json()["id"]
        _seed(session_factory, email="viewer@example.com", role="viewer",
              project_id=uuid.UUID(project_id))
        _seed(session_factory, email="reviewer@example.com", role="reviewer",
              project_id=uuid.UUID(project_id))

        app.state.settings = _settings(auth_enabled=True)

        def token_for(email: str) -> dict:
            token = client.post(
                "/auth/login", json={"email": email, "password": PASSWORD}
            ).json()["access_token"]
            return {"Authorization": f"Bearer {token}"}

        viewer = token_for("viewer@example.com")
        reviewer = token_for("reviewer@example.com")

        # Reading is permitted for both.
        assert client.get(f"/projects/{project_id}/documents", headers=viewer).status_code == 200
        assert client.get(f"/projects/{project_id}/documents", headers=reviewer).status_code == 200

        # A POST is refused for the viewer before the route body ever runs.
        blocked = client.post(
            f"/projects/{project_id}/query-plan",
            json={"question": "anything", "history": []},
            headers=viewer,
        )
        assert blocked.status_code == 403

        allowed = client.post(
            f"/projects/{project_id}/query-plan",
            json={"question": "Show critical path delay risk.", "history": []},
            headers=reviewer,
        )
        assert allowed.status_code == 200


def test_deactivated_user_loses_access_immediately(engine) -> None:
    """The token is still valid, so the check must consult the database."""
    with TestClient(app) as client:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        app.state.session_factory = session_factory
        app.state.settings = _settings(auth_enabled=False)
        project_id = client.post("/projects", json={"name": "Deactivation"}).json()["id"]
        user_id = _seed(session_factory, email="leaver@example.com", role="admin",
                        project_id=uuid.UUID(project_id))

        app.state.settings = _settings(auth_enabled=True)
        token = client.post(
            "/auth/login", json={"email": "leaver@example.com", "password": PASSWORD}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get(f"/projects/{project_id}/documents", headers=headers).status_code == 200

        async def deactivate() -> None:
            async with session_factory() as session:
                user = await session.get(User, user_id)
                user.is_active = False
                await session.commit()

        asyncio.run(deactivate())

        assert client.get(f"/projects/{project_id}/documents", headers=headers).status_code == 401


def test_login_does_not_reveal_whether_an_email_exists(engine) -> None:
    with TestClient(app) as client:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        app.state.session_factory = session_factory
        app.state.settings = _settings(auth_enabled=False)
        project_id = client.post("/projects", json={"name": "Enumeration"}).json()["id"]
        _seed(session_factory, email="known@example.com", role="viewer",
              project_id=uuid.UUID(project_id))

        app.state.settings = _settings(auth_enabled=True)
        wrong_password = client.post(
            "/auth/login", json={"email": "known@example.com", "password": "not the password"}
        )
        unknown_email = client.post(
            "/auth/login", json={"email": "nobody@example.com", "password": "not the password"}
        )

        assert wrong_password.status_code == unknown_email.status_code == 401
        assert wrong_password.json() == unknown_email.json()


def test_creating_users_requires_an_admin(engine) -> None:
    with TestClient(app) as client:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        app.state.session_factory = session_factory
        app.state.settings = _settings(auth_enabled=False)
        project_id = client.post("/projects", json={"name": "Admin gate"}).json()["id"]
        _seed(session_factory, email="plain@example.com", role="viewer",
              project_id=uuid.UUID(project_id))
        _seed(session_factory, email="boss@example.com", role="admin",
              project_id=uuid.UUID(project_id))

        app.state.settings = _settings(auth_enabled=True)

        def token_for(email: str) -> dict:
            token = client.post(
                "/auth/login", json={"email": email, "password": PASSWORD}
            ).json()["access_token"]
            return {"Authorization": f"Bearer {token}"}

        payload = {
            "email": "new@example.com",
            "password": "a-sufficiently-long-password",
            "project_id": project_id,
            "role": "viewer",
        }
        assert client.post("/auth/users", json=payload, headers=token_for("plain@example.com")).status_code == 403

        created = client.post("/auth/users", json=payload, headers=token_for("boss@example.com"))
        assert created.status_code == 201, created.text
        assert created.json()["memberships"][0]["project_id"] == project_id

        # Same address twice is a conflict, not a silent second account.
        assert client.post("/auth/users", json=payload, headers=token_for("boss@example.com")).status_code == 409


def test_short_password_is_refused_by_the_api(engine) -> None:
    with TestClient(app) as client:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        app.state.session_factory = session_factory
        app.state.settings = _settings(auth_enabled=False)
        project_id = client.post("/projects", json={"name": "Password policy"}).json()["id"]
        _seed(session_factory, email="boss2@example.com", role="admin",
              project_id=uuid.UUID(project_id))

        app.state.settings = _settings(auth_enabled=True)
        token = client.post(
            "/auth/login", json={"email": "boss2@example.com", "password": PASSWORD}
        ).json()["access_token"]

        response = client.post(
            "/auth/users",
            json={"email": "weak@example.com", "password": "short", "project_id": project_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422


def test_creating_a_project_grants_the_creator_access(engine) -> None:
    """
    Every project-scoped route needs a membership row, so without one the
    creator lost the project the moment they made it: it existed, it appeared in
    the list, and everything else answered "Project not found".
    """
    with TestClient(app) as client:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        app.state.session_factory = session_factory
        app.state.settings = _settings(auth_enabled=False)
        seed_project = client.post("/projects", json={"name": "Bootstrap"}).json()["id"]
        _seed(session_factory, email="owner@example.com", role="admin",
              project_id=uuid.UUID(seed_project))

        app.state.settings = _settings(auth_enabled=True)
        token = client.post(
            "/auth/login", json={"email": "owner@example.com", "password": PASSWORD}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        created = client.post("/projects", json={"name": "Mine to keep"}, headers=headers)
        assert created.status_code == 201, created.text
        new_id = created.json()["id"]

        # The point: the creator can immediately use what they created.
        assert client.get(f"/projects/{new_id}/documents", headers=headers).status_code == 200


def test_project_list_shows_only_projects_the_caller_belongs_to(engine) -> None:
    """
    Listing every project leaked other tenants' names and ids - the same
    disclosure that answering 404 rather than 403 elsewhere exists to prevent.
    """
    with TestClient(app) as client:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        app.state.session_factory = session_factory
        app.state.settings = _settings(auth_enabled=False)
        mine = client.post("/projects", json={"name": "Visible to me"}).json()["id"]
        theirs = client.post("/projects", json={"name": "Someone else's secret"}).json()["id"]
        _seed(session_factory, email="member@example.com", role="viewer",
              project_id=uuid.UUID(mine))

        app.state.settings = _settings(auth_enabled=True)
        token = client.post(
            "/auth/login", json={"email": "member@example.com", "password": PASSWORD}
        ).json()["access_token"]

        listed = client.get("/projects", headers={"Authorization": f"Bearer {token}"})
        assert listed.status_code == 200
        names = [item["name"] for item in listed.json()]
        ids = [item["id"] for item in listed.json()]
        assert "Visible to me" in names
        assert "Someone else's secret" not in names
        assert theirs not in ids


def test_disabled_auth_still_lists_every_project(engine) -> None:
    """The membership filter must not change behaviour while auth is off."""
    with TestClient(app) as client:
        app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
        app.state.settings = _settings(auth_enabled=False)
        client.post("/projects", json={"name": "One"})
        client.post("/projects", json={"name": "Two"})
        names = [item["name"] for item in client.get("/projects").json()]
        assert "One" in names and "Two" in names
