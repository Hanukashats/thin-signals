"""append-only adversarial review events

Revision ID: e2c7f6a9b104
Revises: 90f5cc54dd46
Create Date: 2026-10-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e2c7f6a9b104"
down_revision = "90f5cc54dd46"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("candidate_id", sa.String(length=64), nullable=False),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("output_hash", sa.String(length=64), nullable=False),
        sa.Column("template_version", sa.String(length=64), nullable=False),
        sa.Column("template_hash", sa.String(length=64), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("provider_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("evidence_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("budget", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False,
        ),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id", "round", "sequence", name="uq_review_event_run_round_sequence",
        ),
    )
    op.create_index(op.f("ix_review_events_candidate_id"), "review_events", ["candidate_id"])
    op.create_index(op.f("ix_review_events_role"), "review_events", ["role"])
    op.create_index(op.f("ix_review_events_run_id"), "review_events", ["run_id"])
    op.add_column("decisions", sa.Column("review_event_id", sa.String(length=64), nullable=True))
    op.create_foreign_key(
        "fk_decisions_review_event_id",
        "decisions",
        "review_events",
        ["review_event_id"],
        ["id"],
    )
    op.create_index(op.f("ix_decisions_review_event_id"), "decisions", ["review_event_id"])
    op.execute("""
        CREATE FUNCTION thin_signals_review_events_append_only()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'review_events is append-only';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER review_events_append_only
        BEFORE UPDATE OR DELETE ON review_events
        FOR EACH ROW EXECUTE FUNCTION thin_signals_review_events_append_only()
    """)


def downgrade() -> None:
    op.drop_index(op.f("ix_decisions_review_event_id"), table_name="decisions")
    op.drop_constraint("fk_decisions_review_event_id", "decisions", type_="foreignkey")
    op.drop_column("decisions", "review_event_id")
    op.execute("DROP TRIGGER review_events_append_only ON review_events")
    op.execute("DROP FUNCTION thin_signals_review_events_append_only()")
    op.drop_index(op.f("ix_review_events_run_id"), table_name="review_events")
    op.drop_index(op.f("ix_review_events_role"), table_name="review_events")
    op.drop_index(op.f("ix_review_events_candidate_id"), table_name="review_events")
    op.drop_table("review_events")
