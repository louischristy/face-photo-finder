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

    sources: Mapped[list["DriveSource"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class DriveSource(Base):
    __tablename__ = "drive_sources"
    __table_args__ = (UniqueConstraint("project_id", "folder_id", name="uq_project_folder"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    folder_url: Mapped[str] = mapped_column(Text)
    folder_id: Mapped[str] = mapped_column(String(200), index=True)
    display_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    project: Mapped[Project] = relationship(back_populates="sources")


class Photo(Base):
    __tablename__ = "photos"
    __table_args__ = (UniqueConstraint("project_id", "drive_file_id", name="uq_project_drive_file"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("drive_sources.id", ondelete="CASCADE"), index=True)
    drive_file_id: Mapped[str] = mapped_column(String(200), index=True)
    name: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(100))
    modified_time: Mapped[str | None] = mapped_column(String(100), nullable=True)
    web_view_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    indexed: Mapped[bool] = mapped_column(Boolean, default=False)
    face_count: Mapped[int] = mapped_column(Integer, default=0)
