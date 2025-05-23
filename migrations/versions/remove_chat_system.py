"""Remove chat system

Revision ID: remove_chat_system
Revises:
Create Date: 2024-12-22 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'remove_chat_system'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Drop the message table first (due to foreign key constraint)
    op.drop_table('message')

    # Drop the chat_session table
    op.drop_table('chat_session')


def downgrade():
    # Recreate chat_session table
    op.create_table('chat_session',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('donor_id', sa.Integer(), nullable=False),
        sa.Column('receiver_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_message_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['donor_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['receiver_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Recreate message table
    op.create_table('message',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chat_session_id', sa.Integer(), nullable=False),
        sa.Column('sender_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('attachment_url', sa.String(length=500), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['chat_session_id'], ['chat_session.id'], ),
        sa.ForeignKeyConstraint(['sender_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )