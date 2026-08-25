"""
Create an account and grant it a project role, directly against the database.

This exists because POST /auth/users requires an existing admin, so the first
account cannot be created through the API. Run it before setting
ATLAS_AUTH_ENABLED=true, or the deployment will have authentication switched on
and nobody able to sign in.

    # first admin on a project
    python3 scripts/create_user.py --email you@example.com \
        --project-id <uuid> --role admin

    # additional account, read-only
    python3 scripts/create_user.py --email judge@example.com \
        --project-id <uuid> --role viewer

    # grant an existing account access to another project
    python3 scripts/create_user.py --email you@example.com \
        --project-id <other-uuid> --role admin

The password is read from the ATLAS_BOOTSTRAP_PASSWORD environment variable, or
prompted for without echo. It is never taken as a command-line argument, which
would put it in shell history and in the process list.

On the deployed instance:

    docker compose -f docker-compose.aws.yml --env-file .env.aws \
      exec -it api python3 scripts/create_user.py --email you@example.com \
      --project-id <uuid> --role admin
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
import uuid
from pathlib import Path

# Running this as a file puts scripts/ on sys.path, not the repository root, so
# `import app` fails. The image deliberately does not pip-install the package -
# the API imports it from the working directory via `python -m uvicorn` - which
# leaves this script to put the root on the path itself. Without this the only
# working invocation was PYTHONPATH=/app, which is not what the docstring said.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import select

from app.auth import ROLE_ORDER, hash_password
from app.config import get_settings
from app.database import create_database_engine, create_session_factory
from app.models import Project, ProjectMember, User

MIN_PASSWORD_LENGTH = 12


async def run(email: str, password: str, project_id: uuid.UUID | None, role: str) -> int:
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    try:
        async with session_factory() as session:
            if project_id is not None:
                project = await session.get(Project, project_id)
                if project is None:
                    print(f"error: no project with id {project_id}", file=sys.stderr)
                    return 1

            user = await session.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(email=email, password_hash=hash_password(password), is_active=True)
                session.add(user)
                await session.flush()
                print(f"created user {email} ({user.id})")
            else:
                # Re-running with a new password is a deliberate reset path: it
                # is the only way back in if the first admin's password is lost.
                user.password_hash = hash_password(password)
                user.is_active = True
                print(f"updated password for existing user {email} ({user.id})")

            if project_id is not None:
                membership = await session.scalar(
                    select(ProjectMember).where(
                        ProjectMember.user_id == user.id,
                        ProjectMember.project_id == project_id,
                    )
                )
                if membership is None:
                    session.add(
                        ProjectMember(project_id=project_id, user_id=user.id, role=role)
                    )
                    print(f"granted {role} on project {project_id}")
                else:
                    membership.role = role
                    print(f"updated role to {role} on project {project_id}")

            await session.commit()
    finally:
        await engine.dispose()

    if not settings.auth_enabled:
        print(
            "\nnote: ATLAS_AUTH_ENABLED is currently false, so this account is not yet\n"
            "      required for access. Set it to true and restart the API to enforce it."
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument(
        "--project-id",
        help="grant a role on this project; omit to create the account only",
    )
    parser.add_argument("--role", default="admin", choices=sorted(ROLE_ORDER))
    args = parser.parse_args()

    email = args.email.strip().lower()
    if "@" not in email:
        print("error: --email does not look like an address", file=sys.stderr)
        return 1

    project_id: uuid.UUID | None = None
    if args.project_id:
        try:
            project_id = uuid.UUID(args.project_id)
        except ValueError:
            print("error: --project-id is not a valid UUID", file=sys.stderr)
            return 1

    password = os.environ.get("ATLAS_BOOTSTRAP_PASSWORD") or ""
    if not password:
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Confirm password: "):
            print("error: passwords do not match", file=sys.stderr)
            return 1

    if len(password) < MIN_PASSWORD_LENGTH:
        print(
            f"error: password must be at least {MIN_PASSWORD_LENGTH} characters",
            file=sys.stderr,
        )
        return 1

    return asyncio.run(run(email, password, project_id, args.role))


if __name__ == "__main__":
    sys.exit(main())
