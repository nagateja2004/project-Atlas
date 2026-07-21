"""Allow NCRs to originate from compliance findings."""

from alembic import op
import sqlalchemy as sa

revision = "20260721_04"
down_revision = "20260721_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"]: column for column in sa.inspect(bind).get_columns("non_conformances")}
    if "compliance_finding_id" not in columns:
        op.add_column("non_conformances", sa.Column("compliance_finding_id", sa.Uuid(), nullable=True))
        op.create_index(
            "ix_non_conformances_compliance_finding_id", "non_conformances", ["compliance_finding_id"]
        )
        if bind.dialect.name != "sqlite":
            op.create_foreign_key(
                "fk_non_conformances_compliance_finding",
                "non_conformances",
                "compliance_findings",
                ["compliance_finding_id"],
                ["id"],
            )
    nullable_changes = [name for name in ("test_record_id", "procedure_document_id") if not columns[name]["nullable"]]
    if nullable_changes:
        with op.batch_alter_table("non_conformances") as batch:
            for name in nullable_changes:
                batch.alter_column(name, existing_type=sa.Uuid(), nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    with op.batch_alter_table("non_conformances") as batch:
        if bind.dialect.name != "sqlite":
            batch.drop_constraint("fk_non_conformances_compliance_finding", type_="foreignkey")
        batch.drop_index("ix_non_conformances_compliance_finding_id")
        batch.drop_column("compliance_finding_id")
        batch.alter_column("procedure_document_id", existing_type=sa.Uuid(), nullable=False)
        batch.alter_column("test_record_id", existing_type=sa.Uuid(), nullable=False)
