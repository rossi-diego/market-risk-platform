# Baseline migration. Schema was provisioned outside Alembic (via Supabase
# Studio/MCP). Future migrations evolve from this point.
"""baseline — schema created via Supabase Studio

Revision ID: 1cc77bf6eb68
Revises:
Create Date: 2026-04-17 13:10:15.179501

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "1cc77bf6eb68"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema — no-op (baseline)."""
    pass


def downgrade() -> None:
    """Downgrade schema — no-op (baseline)."""
    pass
