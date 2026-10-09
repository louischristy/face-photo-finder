from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.runtime import application_data_dir

DATA_DIR = application_data_dir()
DATABASE_URL = f"sqlite:///{DATA_DIR / 'face_photo_finder.sqlite3'}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session():
    with SessionLocal() as session:
        yield session
