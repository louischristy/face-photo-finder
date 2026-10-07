from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    public_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sources: Mapped[list["PhotoSource"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class StorageAccount(Base):
    """A reusable authenticated cloud-storage identity, e.g. one Google account."""
    __tablename__ = "storage_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), index=True)  # google_drive initially
    label: Mapped[str] = mapped_column(String(200))
    account_hint: Mapped[str | None] = mapped_column(String(300), nullable=True)
    token_key: Mapped[str | None] = mapped_column(String(300), nullable=True, unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PhotoSource(Base):
    """A project input. Sources can be cloud folders, local folders, or external drives."""
    __tablename__ = "photo_sources"
    __table_args__ = (UniqueConstraint("project_id", "source_type", "source_key", name="uq_project_source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[str] = mapped_column(String(50), index=True)  # google_drive, local_folder
    source_key: Mapped[str] = mapped_column(Text)  # Drive folder ID or normalized local path
    source_uri: Mapped[str] = mapped_column(Text)  # original Drive URL or local path
    display_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    storage_account_id: Mapped[int | None] = mapped_column(ForeignKey("storage_accounts.id"), nullable=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    removable_media: Mapped[bool] = mapped_column(Boolean, default=False)
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    project: Mapped[Project] = relationship(back_populates="sources")
    storage_account: Mapped[StorageAccount | None] = relationship()


class Photo(Base):
    __tablename__ = "photos"
    __table_args__ = (UniqueConstraint("project_id", "source_id", "source_item_key", name="uq_project_source_item"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("photo_sources.id", ondelete="CASCADE"), index=True)
    source_item_key: Mapped[str] = mapped_column(String(1000), index=True)  # Drive file ID or relative local path
    name: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(100))
    modified_time: Mapped[str | None] = mapped_column(String(100), nullable=True)
    original_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    indexed: Mapped[bool] = mapped_column(Boolean, default=False)
    face_count: Mapped[int] = mapped_column(Integer, default=0)
