"""Synchronous incident persistence operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from recallops.models.incident import Incident
from recallops.schemas.incident import IncidentCreate


class IncidentPersistenceError(RuntimeError):
    """Safe boundary error that does not expose driver details."""


def create_incident(session: Session, payload: IncidentCreate) -> Incident:
    incident = Incident(**payload.model_dump())
    try:
        session.add(incident)
        session.commit()
        session.refresh(incident)
    except SQLAlchemyError:
        session.rollback()
        raise IncidentPersistenceError("Incident persistence failed") from None
    return incident


def list_incidents(session: Session) -> list[Incident]:
    statement = select(Incident).order_by(
        Incident.created_at.desc(),
        Incident.id.desc(),
    )
    try:
        return list(session.scalars(statement).all())
    except SQLAlchemyError:
        session.rollback()
        raise IncidentPersistenceError("Incident persistence failed") from None


def get_incident(session: Session, incident_id: UUID) -> Incident | None:
    try:
        return session.get(Incident, incident_id)
    except SQLAlchemyError:
        session.rollback()
        raise IncidentPersistenceError("Incident persistence failed") from None
