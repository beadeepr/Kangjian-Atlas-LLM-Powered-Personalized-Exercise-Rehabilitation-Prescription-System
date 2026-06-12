from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BASE_DIR = Path(__file__).resolve().parents[1]
SQLALCHEMY_DATABASE_URL = f"sqlite:///{BASE_DIR / 'database.db'}"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    from .models import Base

    Base.metadata.create_all(bind=engine)
