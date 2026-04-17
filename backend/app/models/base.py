from datetime import datetime
from enum import Enum as PyEnum
from typing import TypeVar

from sqlalchemy import DateTime, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

_E = TypeVar("_E", bound=PyEnum)


def pg_enum(py_enum: type[_E], name: str) -> SAEnum:
    """Wrap a Python enum as a Postgres native enum column.

    Uses `values_callable` so SQLAlchemy serializes by `.value` (lowercase)
    instead of the default `.name` (uppercase). Matches the Postgres enum
    values defined in `supabase/migrations/*.sql`.
    """
    return SAEnum(
        py_enum,
        name=name,
        native_enum=True,
        create_type=False,
        values_callable=lambda e: [m.value for m in e],
    )


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
