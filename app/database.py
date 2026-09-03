import os
from sqlmodel import SQLModel, create_engine, Session

DB_PATH = os.environ.get("FREEZE_DB_PATH", "freeze.db")
# Default pool (5 + 10 overflow = 15 connections) turned polling bursts into
# a hard cliff around ~60 concurrent requests instead of graceful slowdown -
# raised well above realistic engineer-count bursts.
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    pool_size=50,
    max_overflow=150,
)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
