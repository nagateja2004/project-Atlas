"""Add compliance review notes and source revision fields."""

from alembic import op
import sqlalchemy as sa

revision = "20260721_02"
down_revision = "20260721_01"
branch_labels = None
depends_on = None

COLUMNS = (
    sa.Column("reviewer_note", sa.Text(), nullable=True),
    sa.Column("specification_revision", sa.String(50), nullable=True),
    sa.Column("specification_approval_status", sa.String(50), nullable=True),
    sa.Column("submittal_revision", sa.String(50), nullable=True),
    sa.Column("submittal_approval_status", sa.String(50), nullable=True),
)


def upgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("compliance_findings")}
    for column in COLUMNS:
        if column.name not in existing:
            op.add_column("compliance_findings", column)


def downgrade() -> None:
    for column in reversed(COLUMNS):
        op.drop_column("compliance_findings", column.name)
