"""user profile photo

Revision ID: a7c3e91f2b40
Revises: eeeb3959ae84
Create Date: 2026-09-30 15:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7c3e91f2b40'
down_revision = 'eeeb3959ae84'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('avatar', sa.LargeBinary(), nullable=True))
        batch_op.add_column(sa.Column('avatar_updated_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('avatar_updated_at')
        batch_op.drop_column('avatar')
