"""Track counterfactual mitigation simulations and selections."""

from alembic import op
import sqlalchemy as sa

revision = "20260721_08"
down_revision = "20260721_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("mitigation_scenarios")}
    additions = (
        sa.Column("simulation_id", sa.Uuid(), nullable=True),
        sa.Column("scenario_key", sa.String(50), nullable=True),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column in additions:
        if column.name not in columns:
            op.add_column("mitigation_scenarios", column)
    indexes = {item["name"] for item in inspector.get_indexes("mitigation_scenarios")}
    if "ix_mitigation_scenarios_simulation_id" not in indexes:
        op.create_index("ix_mitigation_scenarios_simulation_id", "mitigation_scenarios", ["simulation_id"])


def downgrade() -> None:
    with op.batch_alter_table("mitigation_scenarios") as batch:
        batch.drop_index("ix_mitigation_scenarios_simulation_id")
        batch.drop_column("selected_at")
        batch.drop_column("scenario_key")
        batch.drop_column("simulation_id")
