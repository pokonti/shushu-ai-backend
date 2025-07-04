"""Create initial tables

Revision ID: 9c3242b53847
Revises: 
Create Date: 2025-07-02 18:56:35.206267

"""
import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c3242b53847'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('username', sa.String, nullable=True, unique=True, index=True),
        sa.Column('email', sa.String, nullable=False, unique=True, index=True),
        sa.Column('hashed_password', sa.String, nullable=True),
        sa.Column('google_id', sa.String, unique=True, index=True, nullable=True),
        sa.Column('avatar_url', sa.String, nullable=True),
        sa.Column('created_at', sa.DateTime, default=datetime.datetime.utcnow),
    )

    op.create_table(
        'audios',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('file_path', sa.String, nullable=False),
        sa.Column('uploaded_at', sa.DateTime, default=datetime.datetime.utcnow),
        sa.Column('object_name', sa.Text, nullable=False),
        sa.Column('public_url', sa.Text, nullable=True),
        sa.Column('status', sa.String, default='PENDING'),
        sa.Column('summary', sa.String, nullable=True),
        sa.Column('error_message', sa.String, nullable=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
    )

    op.create_table(
        'videos',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('file_path', sa.String, nullable=False),
        sa.Column('uploaded_at', sa.DateTime, default=datetime.datetime.utcnow),
        sa.Column('object_name', sa.Text, nullable=False),
        sa.Column('public_url', sa.Text, nullable=True),
        sa.Column('status', sa.String, default='PENDING'),
        sa.Column('summary', sa.String, nullable=True),
        sa.Column('error_message', sa.String, nullable=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('videos')
    op.drop_table('audios')
    op.drop_table('users')