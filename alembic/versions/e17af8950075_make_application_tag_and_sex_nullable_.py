"""make application tag and sex nullable fields

Revision ID: e17af8950075
Revises: 3a97578f207c
Create Date: 2017-05-02 15:38:18.430426

"""
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'e17af8950075'
down_revision = '3a97578f207c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('sample', 'apptag_id',
                    existing_type=mysql.INTEGER(display_width=11), nullable=True)
    op.alter_column('sample', 'sex',
                    existing_type=mysql.ENUM('male', 'female', 'unknown'), nullable=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('sample', 'sex',
                    existing_type=mysql.ENUM('male', 'female', 'unknown'), nullable=False)
    op.alter_column('sample', 'apptag_id',
                    existing_type=mysql.INTEGER(display_width=11), nullable=False)
    # ### end Alembic commands ###
