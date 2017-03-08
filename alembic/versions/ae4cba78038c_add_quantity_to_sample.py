"""add quantity to sample

Revision ID: ae4cba78038c
Revises: b9a793f4a131
Create Date: 2017-03-08 16:27:24.901137

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ae4cba78038c'
down_revision = 'b9a793f4a131'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('sample', sa.Column('quantity', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('sample', 'quantity')
    # ### end Alembic commands ###
