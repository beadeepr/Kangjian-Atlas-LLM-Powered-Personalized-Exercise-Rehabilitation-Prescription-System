from pathlib import Path
import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

BASE_DIR = Path(__file__).resolve().parents[1]
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'database.db'}")

connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    from .models import Base

    Base.metadata.create_all(bind=engine)
    if is_sqlite_database():
        _ensure_sqlite_columns()


def is_sqlite_database() -> bool:
    return SQLALCHEMY_DATABASE_URL.startswith("sqlite")


def database_backend() -> dict:
    url_prefix = SQLALCHEMY_DATABASE_URL.split(":", 1)[0]
    return {
        "driver": url_prefix,
        "is_sqlite": is_sqlite_database(),
        "url_configured": bool(os.getenv("DATABASE_URL")),
    }


def check_database() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _ensure_sqlite_columns():
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "prescriptions" not in table_names:
        return
    columns = {column["name"] for column in inspector.get_columns("prescriptions")}
    statements = []
    if "raw_response" not in columns:
        statements.append("ALTER TABLE prescriptions ADD COLUMN raw_response JSON")
    if "user_id" not in columns:
        statements.append("ALTER TABLE prescriptions ADD COLUMN user_id INTEGER")
    if "patient_profile_id" not in columns:
        statements.append("ALTER TABLE prescriptions ADD COLUMN patient_profile_id INTEGER")

    if "users" in table_names:
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "role" not in user_columns:
            statements.append("ALTER TABLE users ADD COLUMN role VARCHAR(32) NOT NULL DEFAULT 'user'")

    if not statements:
        return
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
