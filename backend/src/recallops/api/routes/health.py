"""Process and database health endpoints."""

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, status

from recallops.database.health import check_database_connection

router = APIRouter(prefix="/health", tags=["health"])
DatabaseHealthChecker = Callable[[], None]


def get_database_health_checker() -> DatabaseHealthChecker:
    """Provide an overridable database health operation."""

    return check_database_connection


@router.get("")
def health() -> dict[str, str]:
    """Report process health without depending on the database."""

    return {"status": "ok", "service": "recallops-api"}


@router.get("/database")
def database_health(
    checker: DatabaseHealthChecker = Depends(get_database_health_checker),
) -> dict[str, str]:
    """Report database reachability without exposing connection details."""

    try:
        checker()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from None
    return {"status": "ok", "database": "reachable"}
