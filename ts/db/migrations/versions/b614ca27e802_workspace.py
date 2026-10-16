"""Add a single shared workspace pointer. Delivery package date: 2026-09-29."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b614ca27e802"
down_revision = "e2c7f6a9b104"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "workspace",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("runs.id", ondelete="SET NULL")),
        sa.Column("archive", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("id = 1", name="workspace_singleton"),
    )


def downgrade():
    op.drop_table("workspace")
