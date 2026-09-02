from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, MetaData, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Fix applied here: Add schema="public" to metadata globally
metadata = MetaData(naming_convention=NAMING_CONVENTION, schema="public")

class Base(DeclarativeBase):
    """Shared abstract base class implementing the global metadata configuration."""
    metadata = metadata

class UUIDPrimaryKeyMixin:
    """Provide a UUID primary key."""
    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

class TimestampMixin:
    """Track when a database record was created and last updated."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

class VersionedMixin:
    """Enable SQLAlchemy optimistic concurrency checking."""
    version: Mapped[int] = mapped_column(
        nullable=False,
        default=1,
        server_default="1",
    )

    @declared_attr.directive
    def __mapper_args__(cls) -> dict[str, object]:
        return {
            "version_id_col": cls.version,
        }

class UUIDTimestampVersionMixin(UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin):
    """Combine the UUID primary key, timestamp, and version mixins."""
    
