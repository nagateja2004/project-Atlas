"""Add project-scoped shipment timeline and schedule exposure fields."""

from alembic import op
import sqlalchemy as sa

revision = "20260721_07"
down_revision = "20260721_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    shipment_columns = {column["name"] for column in inspector.get_columns("shipments")}
    additions = (
        sa.Column("required_on_site_date", sa.Date(), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("available_float_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("schedule_task_id", sa.String(100), nullable=True),
        sa.Column("first_alert_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column in additions:
        if column.name not in shipment_columns:
            op.add_column("shipments", column)
    indexes = {item["name"] for item in inspector.get_indexes("shipments")}
    if "ix_shipments_schedule_task_id" not in indexes:
        op.create_index("ix_shipments_schedule_task_id", "shipments", ["schedule_task_id"])
    task_columns = {column["name"] for column in inspector.get_columns("schedule_tasks")}
    if "available_float_days" not in task_columns:
        op.add_column(
            "schedule_tasks",
            sa.Column("available_float_days", sa.Integer(), nullable=False, server_default="0"),
        )
    if "shipment_events" not in inspector.get_table_names():
        op.create_table(
            "shipment_events",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("shipment_id", sa.Uuid(), sa.ForeignKey("shipments.id"), nullable=False),
            sa.Column("equipment_id", sa.String(100), nullable=False),
            sa.Column("event_type", sa.String(50), nullable=False),
            sa.Column("status", sa.String(50), nullable=False),
            sa.Column("location", sa.String(255), nullable=True),
            sa.Column("event_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("details", sa.JSON(), nullable=False, server_default="{}"),
        )
        for column in ("project_id", "shipment_id", "equipment_id"):
            op.create_index(f"ix_shipment_events_{column}", "shipment_events", [column])


def downgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    if "shipment_events" in existing:
        op.drop_table("shipment_events")
    with op.batch_alter_table("schedule_tasks") as batch:
        batch.drop_column("available_float_days")
    with op.batch_alter_table("shipments") as batch:
        batch.drop_index("ix_shipments_schedule_task_id")
        for column in (
            "first_alert_at", "schedule_task_id", "available_float_days", "location", "required_on_site_date",
        ):
            batch.drop_column(column)
