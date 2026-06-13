from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

BASE_DIR = Path(__file__).resolve().parents[1]
SQLALCHEMY_DATABASE_URL = f"sqlite:///{BASE_DIR / 'database.db'}"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    from .models import Base

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


def _ensure_sqlite_columns():
    inspector = inspect(engine)
    if "prescriptions" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("prescriptions")}
    statements = []
    if "raw_response" not in columns:
        statements.append("ALTER TABLE prescriptions ADD COLUMN raw_response JSON")
    if "user_id" not in columns:
        statements.append("ALTER TABLE prescriptions ADD COLUMN user_id INTEGER")

    if not statements:
        return
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
