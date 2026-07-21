"""Add project-scoped workflow timing benchmarks."""

from alembic import op
import sqlalchemy as sa

revision = "20260721_09"
down_revision = "20260721_08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "workflow_benchmarks" in inspector.get_table_names():
        return
    op.create_table(
        "workflow_benchmarks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_type", sa.String(60), nullable=False),
        sa.Column("manual_baseline_seconds", sa.Float(), nullable=False),
        sa.Column("atlas_execution_seconds", sa.Float(), nullable=False),
        sa.Column("measurement_source", sa.String(255), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("measurement_kind", sa.String(20), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("synthetic_data", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_benchmarks_project_id", "workflow_benchmarks", ["project_id"])
    op.create_index("ix_workflow_benchmarks_workflow_type", "workflow_benchmarks", ["workflow_type"])
    op.create_index("ix_workflow_benchmarks_measurement_kind", "workflow_benchmarks", ["measurement_kind"])


def downgrade() -> None:
    op.drop_table("workflow_benchmarks")
