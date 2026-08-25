"""Separate identity from project access, and add credentials.

`users` previously carried `project_id` and `role`, so an account belonged to
exactly one project and there was no way to sign in by email alone. Identity and
access are now separate: `users` is a global credential and `project_members`
grants it a role per project.

The table was never populated by any code path, so there is nothing to migrate -
the old columns are dropped rather than backfilled. Every step is guarded by an
inspector because migration 20260721_01 bootstraps the whole schema from live
`Base.metadata`, which means a fresh database already arrives in the new shape
and must not be altered twice.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260824_10"
down_revision = "20260721_09"
branch_labels = None
depends_on = None


def _columns(inspector, table: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "users" not in tables:
        # Nothing to reshape; models.py owns the definition and migration 01
        # will have created it from metadata.
        return

    existing = _columns(inspector, "users")

    # --- credentials -------------------------------------------------------
    if "password_hash" not in existing:
        op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))

    if "is_active" not in existing:
        op.add_column(
            "users",
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        )

    # --- identity becomes global ------------------------------------------
    unique_names = {c["name"] for c in inspector.get_unique_constraints("users")}
    if "uq_users_project_email" in unique_names:
        op.drop_constraint("uq_users_project_email", "users", type_="unique")

    if "role" in existing:
        # Superseded by project_members.role. Dropped rather than migrated
        # because no row ever existed to carry a value.
        op.drop_column("users", "role")

    if "project_id" in existing:
        # Postgres removes the dependent index and foreign key with the column.
        op.drop_column("users", "project_id")

    index_names = {index["name"] for index in inspector.get_indexes("users")}
    if "ix_users_email" not in index_names:
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- access ------------------------------------------------------------
    if "project_members" not in tables:
        op.create_table(
            "project_members",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("project_id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("role", sa.String(50), nullable=False, server_default="viewer"),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
            ),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("project_id", "user_id", name="uq_project_members_project_user"),
        )
        op.create_index("ix_project_members_project_id", "project_members", ["project_id"])
        op.create_index("ix_project_members_user_id", "project_members", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "project_members" in tables:
        op.drop_index("ix_project_members_user_id", table_name="project_members")
        op.drop_index("ix_project_members_project_id", table_name="project_members")
        op.drop_table("project_members")

    if "users" not in tables:
        return

    index_names = {index["name"] for index in inspector.get_indexes("users")}
    if "ix_users_email" in index_names:
        op.drop_index("ix_users_email", table_name="users")

    existing = _columns(inspector, "users")

    # Restored nullable: the original column was NOT NULL, but there is no
    # project to attribute an existing row to, and failing the downgrade on a
    # populated table would be worse than a relaxed constraint.
    if "project_id" not in existing:
        op.add_column("users", sa.Column("project_id", sa.Uuid(), nullable=True))
        op.create_index("ix_users_project_id", "users", ["project_id"])

    if "role" not in existing:
        op.add_column("users", sa.Column("role", sa.String(50), nullable=True, server_default="member"))

    if "is_active" in existing:
        op.drop_column("users", "is_active")

    if "password_hash" in existing:
        op.drop_column("users", "password_hash")
