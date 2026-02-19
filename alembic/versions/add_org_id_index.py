"""add index on translation_jobs.org_id

Revision ID: b1c2d3e4f5a6
Revises: e3ad6dbcdf0c
Create Date: 2026-02-19

"""
from alembic import op

revision = 'b1c2d3e4f5a6'
down_revision = 'e3ad6dbcdf0c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index('ix_translation_jobs_org_id', 'translation_jobs', ['org_id'])


def downgrade() -> None:
    op.drop_index('ix_translation_jobs_org_id', table_name='translation_jobs')
