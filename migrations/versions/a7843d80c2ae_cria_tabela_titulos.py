"""cria tabela titulos

Revision ID: a7843d80c2ae
Revises:
Create Date: 2026-10-11 22:25:35.274066

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7843d80c2ae"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "titulos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cnpj_sacado", sa.String(length=14), nullable=False),
        sa.Column("valor_titulo", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("data_vencimento", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDENTE", "APROVADO", "REJEITADO", name="statustitulo", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_titulos_cnpj_sacado"), "titulos", ["cnpj_sacado"], unique=False)
    op.create_index(op.f("ix_titulos_status"), "titulos", ["status"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_titulos_status"), table_name="titulos")
    op.drop_index(op.f("ix_titulos_cnpj_sacado"), table_name="titulos")
    op.drop_table("titulos")
