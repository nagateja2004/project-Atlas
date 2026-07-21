"""Add structured commissioning step fields."""

from alembic import op
import sqlalchemy as sa

revision = "20260721_03"
down_revision = "20260721_02"
branch_labels = None
depends_on = None

COLUMNS = (
    sa.Column("prerequisite", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column("evidence", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column("reviewer_note", sa.Text(), nullable=True),
)


def upgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("commissioning_steps")}
    for column in COLUMNS:
        if column.name not in existing:
            op.add_column("commissioning_steps", column)


def downgrade() -> None:
    for column in reversed(COLUMNS):
        op.drop_column("commissioning_steps", column.name)
