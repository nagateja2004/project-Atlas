"""Add project-scoped equipment digital thread entities."""

from alembic import op
import sqlalchemy as sa

from app.models import Base

revision = "20260721_01"
down_revision = None
branch_labels = None
depends_on = None

TABLES = (
    "equipment",
    "requirements",
    "vendors",
    "shipments",
    "schedule_tasks",
    "commissioning_steps",
    "rfis",
    "mitigation_scenarios",
    "evidence_links",
)
RELATED = ("documents", "compliance_findings", "commissioning_test_records", "non_conformances")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "projects" not in inspector.get_table_names():
        Base.metadata.create_all(bind)
        return
    for table_name in RELATED:
        if "equipment_id" not in {column["name"] for column in inspector.get_columns(table_name)}:
            op.add_column(table_name, sa.Column("equipment_id", sa.String(100), nullable=True))
            op.create_index(f"ix_{table_name}_equipment_id", table_name, ["equipment_id"])
    # ponytail: current metadata keeps this first migration compact; freeze explicit table DDL before an independent release train.
    for table_name in TABLES:
        Base.metadata.tables[table_name].create(bind, checkfirst=True)


def downgrade() -> None:
    for table_name in reversed(TABLES):
        op.drop_table(table_name)
    for table_name in RELATED:
        op.drop_index(f"ix_{table_name}_equipment_id", table_name=table_name)
        op.drop_column(table_name, "equipment_id")
