"""add boolean field to mark existing samples

Revision ID: 3a97578f207c
Revises: 6c8b7f5cde7d
Create Date: 2017-05-02 13:30:27.590416

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3a97578f207c'
down_revision = '6c8b7f5cde7d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('sample', sa.Column('existing_sample', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('sample', 'existing_sample')
    # ### end Alembic commands ###
