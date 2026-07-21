"""Add evidence-backed impact events and edges."""

from alembic import op
import sqlalchemy as sa

revision = "20260721_05"
down_revision = "20260721_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "impact_events" not in existing:
        op.create_table(
            "impact_events",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("equipment_id", sa.String(100), nullable=False),
            sa.Column("type", sa.String(50), nullable=False),
            sa.Column("source_id", sa.String(255), nullable=False),
            sa.Column("severity", sa.String(20), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
            sa.Column("assumptions", sa.JSON(), nullable=False, server_default="{}"),
        )
        for column in ("project_id", "equipment_id", "type", "source_id"):
            op.create_index(f"ix_impact_events_{column}", "impact_events", [column])
    if "impact_edges" not in existing:
        op.create_table(
            "impact_edges",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("equipment_id", sa.String(100), nullable=False),
            sa.Column("source_event", sa.Uuid(), sa.ForeignKey("impact_events.id"), nullable=False),
            sa.Column("target_event", sa.Uuid(), sa.ForeignKey("impact_events.id"), nullable=False),
            sa.Column("relationship", sa.String(100), nullable=False),
            sa.Column("delay_days", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("confidence", sa.Float(), nullable=False),
        )
        for column in ("project_id", "equipment_id", "source_event", "target_event"):
            op.create_index(f"ix_impact_edges_{column}", "impact_edges", [column])
    if "evidence_records" not in existing:
        op.create_table(
            "evidence_records",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("equipment_id", sa.String(100), nullable=False),
            sa.Column("impact_event_id", sa.Uuid(), sa.ForeignKey("impact_events.id"), nullable=False),
            sa.Column("claim", sa.Text(), nullable=False),
            sa.Column("document", sa.String(512), nullable=False),
            sa.Column("page", sa.Integer(), nullable=True),
            sa.Column("clause", sa.String(255), nullable=True),
            sa.Column("excerpt", sa.Text(), nullable=False),
            sa.Column("model_version", sa.String(100), nullable=False),
            sa.Column("verification_status", sa.String(30), nullable=False),
        )
        for column in ("project_id", "equipment_id", "impact_event_id"):
            op.create_index(f"ix_evidence_records_{column}", "evidence_records", [column])


def downgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    for table in ("evidence_records", "impact_edges", "impact_events"):
        if table in existing:
            op.drop_table(table)
