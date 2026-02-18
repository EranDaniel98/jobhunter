"""Initial schema with all tables and pgvector indexes

Revision ID: 001
Revises:
Create Date: 2026-02-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Candidates
    op.create_table(
        "candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("headline", sa.String(500)),
        sa.Column("location", sa.String(255)),
        sa.Column("target_roles", postgresql.ARRAY(sa.String(255))),
        sa.Column("target_industries", postgresql.ARRAY(sa.String(255))),
        sa.Column("target_locations", postgresql.ARRAY(sa.String(255))),
        sa.Column("salary_min", sa.Integer),
        sa.Column("salary_max", sa.Integer),
        sa.Column("preferences", postgresql.JSONB, default={}),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Resumes
    op.create_table(
        "resumes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("raw_text", sa.Text),
        sa.Column("parsed_data", postgresql.JSONB),
        sa.Column("is_primary", sa.Boolean, default=True),
        sa.Column("version_label", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Candidate DNA
    op.create_table(
        "candidate_dna",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("embedding", Vector(1536)),
        sa.Column("skills_vector", Vector(1536)),
        sa.Column("experience_summary", sa.Text),
        sa.Column("strengths", postgresql.ARRAY(sa.String(255))),
        sa.Column("gaps", postgresql.ARRAY(sa.String(255))),
        sa.Column("career_stage", sa.String(50)),
        sa.Column("transferable_skills", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Skills
    op.create_table(
        "skills",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("proficiency", sa.String(50)),
        sa.Column("years_experience", sa.Float),
        sa.Column("evidence", sa.Text),
        sa.Column("embedding", Vector(1536)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Companies
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False, index=True),
        sa.Column("industry", sa.String(255)),
        sa.Column("size_range", sa.String(50)),
        sa.Column("location_hq", sa.String(255)),
        sa.Column("description", sa.Text),
        sa.Column("tech_stack", postgresql.ARRAY(sa.String(255))),
        sa.Column("funding_stage", sa.String(100)),
        sa.Column("logo_url", sa.String(500)),
        sa.Column("hunter_data", postgresql.JSONB),
        sa.Column("fit_score", sa.Float),
        sa.Column("embedding", Vector(1536)),
        sa.Column("status", sa.String(20), default="suggested", index=True),
        sa.Column("research_status", sa.String(20), default="pending"),
        sa.Column("last_enriched", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Company Dossiers
    op.create_table(
        "company_dossiers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("culture_summary", sa.Text),
        sa.Column("culture_score", sa.Float),
        sa.Column("red_flags", postgresql.ARRAY(sa.String(500))),
        sa.Column("interview_format", sa.Text),
        sa.Column("interview_questions", postgresql.JSONB),
        sa.Column("compensation_data", postgresql.JSONB),
        sa.Column("key_people", postgresql.JSONB),
        sa.Column("why_hire_me", sa.Text),
        sa.Column("recent_news", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Contacts
    op.create_table(
        "contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255)),
        sa.Column("email_verified", sa.Boolean, default=False),
        sa.Column("email_confidence", sa.Float),
        sa.Column("title", sa.String(255)),
        sa.Column("role_type", sa.String(50)),
        sa.Column("linkedin_url", sa.String(500)),
        sa.Column("twitter_handle", sa.String(100)),
        sa.Column("hunter_data", postgresql.JSONB),
        sa.Column("is_decision_maker", sa.Boolean, default=False),
        sa.Column("outreach_priority", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Outreach Messages
    op.create_table(
        "outreach_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("channel", sa.String(20), default="email"),
        sa.Column("message_type", sa.String(20), default="initial"),
        sa.Column("subject", sa.String(500)),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("personalization_data", postgresql.JSONB),
        sa.Column("external_message_id", sa.String(255), index=True),
        sa.Column("status", sa.String(20), default="draft", index=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("opened_at", sa.DateTime(timezone=True)),
        sa.Column("replied_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Message Events
    op.create_table(
        "message_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("outreach_message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("outreach_messages.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("metadata", postgresql.JSONB),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Email Suppressions
    op.create_table(
        "email_suppressions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("reason", sa.String(50), nullable=False),
        sa.Column("suppressed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Analytics Events
    op.create_table(
        "analytics_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("event_type", sa.String(100), nullable=False, index=True),
        sa.Column("entity_type", sa.String(50)),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True)),
        sa.Column("metadata", postgresql.JSONB),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # HNSW indexes for vector similarity search
    op.execute(
        "CREATE INDEX idx_candidate_dna_embedding ON candidate_dna USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 128)"
    )
    op.execute(
        "CREATE INDEX idx_candidate_dna_skills_vector ON candidate_dna USING hnsw (skills_vector vector_cosine_ops) WITH (m = 16, ef_construction = 128)"
    )
    op.execute(
        "CREATE INDEX idx_skills_embedding ON skills USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 128)"
    )
    op.execute(
        "CREATE INDEX idx_companies_embedding ON companies USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 128)"
    )

    # Composite indexes for common queries
    op.create_index("idx_companies_candidate_status", "companies", ["candidate_id", "status"])
    op.create_index("idx_outreach_candidate_status", "outreach_messages", ["candidate_id", "status"])
    op.create_index("idx_analytics_candidate_type", "analytics_events", ["candidate_id", "event_type"])


def downgrade() -> None:
    op.drop_table("analytics_events")
    op.drop_table("email_suppressions")
    op.drop_table("message_events")
    op.drop_table("outreach_messages")
    op.drop_table("contacts")
    op.drop_table("company_dossiers")
    op.drop_table("companies")
    op.drop_table("skills")
    op.drop_table("candidate_dna")
    op.drop_table("resumes")
    op.drop_table("candidates")
    op.execute("DROP EXTENSION IF EXISTS vector")
