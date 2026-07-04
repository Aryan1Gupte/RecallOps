"""Minimal database reachability check."""

from sqlalchemy import text

from recallops.database.session import get_engine


def check_database_connection() -> None:
    """Run a side-effect-free query and raise when the database is unavailable."""

    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
