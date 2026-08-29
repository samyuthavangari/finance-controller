"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-27
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tables are created by SQLAlchemy metadata on startup for demo;
    # this revision documents the contract and is used in production deploys.
    bind = op.get_bind()
    from app.db import Base

    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    from app.db import Base

    Base.metadata.drop_all(bind=bind)
