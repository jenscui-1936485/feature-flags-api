"""add rollout_percent to feature_flags

Revision ID: 002_rollout_percent
Revises: 001_initial
Create Date: 2026-09-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_rollout_percent"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("feature_flags") as batch_op:
        batch_op.add_column(
            sa.Column(
                "rollout_percent",
                sa.Integer(),
                nullable=False,
                server_default="100",
            )
        )
        batch_op.create_check_constraint(
            "ck_feature_flags_rollout_percent",
            "rollout_percent >= 0 AND rollout_percent <= 100",
        )


def downgrade() -> None:
    with op.batch_alter_table("feature_flags") as batch_op:
        batch_op.drop_constraint("ck_feature_flags_rollout_percent", type_="check")
        batch_op.drop_column("rollout_percent")
