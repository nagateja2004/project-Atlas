"""Persist reproducible evaluation runs and cases."""

from alembic import op
import sqlalchemy as sa

revision = "20260721_06"
down_revision = "20260721_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "evaluation_runs" not in existing:
        op.create_table(
            "evaluation_runs",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("fixture_name", sa.String(100), nullable=False),
            sa.Column("fixture_format", sa.String(10), nullable=False),
            sa.Column("synthetic_data", sa.Boolean(), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("metrics", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_evaluation_runs_project_id", "evaluation_runs", ["project_id"])
    if "evaluation_cases" not in existing:
        op.create_table(
            "evaluation_cases",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("evaluation_run_id", sa.Uuid(), sa.ForeignKey("evaluation_runs.id"), nullable=False),
            sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("case_key", sa.String(100), nullable=False),
            sa.Column("category", sa.String(30), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("expected", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("actual", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("metrics", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("error", sa.Text(), nullable=True),
            sa.UniqueConstraint("evaluation_run_id", "case_key", name="uq_evaluation_run_case"),
        )
        op.create_index("ix_evaluation_cases_evaluation_run_id", "evaluation_cases", ["evaluation_run_id"])
        op.create_index("ix_evaluation_cases_project_id", "evaluation_cases", ["project_id"])


def downgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "evaluation_cases" in existing:
        op.drop_table("evaluation_cases")
    if "evaluation_runs" in existing:
        op.drop_table("evaluation_runs")
