"""Database reachability and schema readiness checks."""

from sqlalchemy import inspect
from sqlalchemy import text

from recallops.database.session import get_engine

REQUIRED_TABLES = ("alembic_version", "incidents", "memories")


class DatabaseNotReadyError(RuntimeError):
    """Raised when the database is reachable but required schema is absent."""


def check_database_connection() -> None:
    """Run side-effect-free readiness checks for deployment health."""

    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
        inspector = inspect(connection)
        missing_tables = [
            table_name
            for table_name in REQUIRED_TABLES
            if not inspector.has_table(table_name)
        ]
        if missing_tables:
            raise DatabaseNotReadyError("Database schema is not ready")
