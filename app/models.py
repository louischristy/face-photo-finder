from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
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
    __tablename__ = "storage_accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), index=True)
    label: Mapped[str] = mapped_column(String(200))
    account_hint: Mapped[str | None] = mapped_column(String(300), nullable=True)
    token_key: Mapped[str | None] = mapped_column(String(300), nullable=True, unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PhotoSource(Base):
    __tablename__ = "photo_sources"
    __table_args__ = (UniqueConstraint("project_id", "source_type", "source_key", name="uq_project_source"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[str] = mapped_column(String(50), index=True)
    source_key: Mapped[str] = mapped_column(Text)
    source_uri: Mapped[str] = mapped_column(Text)
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
    source_item_key: Mapped[str] = mapped_column(String(1000), index=True)
    name: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(100))
    modified_time: Mapped[str | None] = mapped_column(String(100), nullable=True)
    original_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    indexed: Mapped[bool] = mapped_column(Boolean, default=False)
    face_count: Mapped[int] = mapped_column(Integer, default=0)


class Face(Base):
    __tablename__ = "faces"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("photo_sources.id", ondelete="CASCADE"), index=True)
    bbox_x: Mapped[int] = mapped_column(Integer)
    bbox_y: Mapped[int] = mapped_column(Integer)
    bbox_w: Mapped[int] = mapped_column(Integer)
    bbox_h: Mapped[int] = mapped_column(Integer)
    detector_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    embedding: Mapped[bytes] = mapped_column(LargeBinary)
    embedding_dim: Mapped[int] = mapped_column(Integer)
    crop_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FaceCluster(Base):
    __tablename__ = "face_clusters"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="candidate")
    representative_face_id: Mapped[int | None] = mapped_column(ForeignKey("faces.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FaceClusterMember(Base):
    __tablename__ = "face_cluster_members"
    __table_args__ = (UniqueConstraint("cluster_id", "face_id", name="uq_cluster_face"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    cluster_id: Mapped[int] = mapped_column(ForeignKey("face_clusters.id", ondelete="CASCADE"), index=True)
    face_id: Mapped[int] = mapped_column(ForeignKey("faces.id", ondelete="CASCADE"), index=True)
    distance: Mapped[float | None] = mapped_column(Float, nullable=True)
