"""Incident CRUD HTTP routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from recallops.ai.bedrock import AnalysisServiceError
from recallops.ai.dependencies import (
    IncidentAnalysisServiceFactory,
    get_incident_analysis_service_factory,
)
from recallops.ai.protocols import IncidentAnalysisInput
from recallops.config import BedrockConfigurationError
from recallops.database.session import get_db
from recallops.repositories.incidents import (
    IncidentPersistenceError,
    create_incident,
    get_incident,
    list_incidents,
)
from recallops.schemas.analysis import IncidentAnalysisResponse
from recallops.schemas.incident import IncidentCreate, IncidentResponse

router = APIRouter(prefix="/incidents", tags=["incidents"])


def persistence_unavailable() -> HTTPException:
    """Create a generic API error that contains no driver details."""

    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Database operation unavailable",
    )


@router.post("", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
def create_incident_endpoint(
    payload: IncidentCreate,
    session: Session = Depends(get_db),
) -> IncidentResponse:
    try:
        return IncidentResponse.model_validate(create_incident(session, payload))
    except IncidentPersistenceError:
        raise persistence_unavailable() from None


@router.get("", response_model=list[IncidentResponse])
def list_incidents_endpoint(
    session: Session = Depends(get_db),
) -> list[IncidentResponse]:
    try:
        return [
            IncidentResponse.model_validate(incident)
            for incident in list_incidents(session)
        ]
    except IncidentPersistenceError:
        raise persistence_unavailable() from None


@router.get("/{incident_id}", response_model=IncidentResponse)
def get_incident_endpoint(
    incident_id: UUID,
    session: Session = Depends(get_db),
) -> IncidentResponse:
    try:
        incident = get_incident(session, incident_id)
    except IncidentPersistenceError:
        raise persistence_unavailable() from None

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )
    return IncidentResponse.model_validate(incident)


@router.post("/{incident_id}/analysis", response_model=IncidentAnalysisResponse)
def analyze_incident_endpoint(
    incident_id: UUID,
    session: Session = Depends(get_db),
    service_factory: IncidentAnalysisServiceFactory = Depends(
        get_incident_analysis_service_factory
    ),
) -> IncidentAnalysisResponse:
    """Generate a validated, non-persisted analysis for one incident."""

    try:
        incident = get_incident(session, incident_id)
    except IncidentPersistenceError:
        raise persistence_unavailable() from None

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    analysis_input = IncidentAnalysisInput(
        incident_id=incident.id,
        title=incident.title,
        description=incident.description,
        service=incident.service,
        environment=incident.environment,
        status=incident.status,
    )

    try:
        service = service_factory()
        return service.analyze(analysis_input)
    except BedrockConfigurationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI analysis is not configured",
        ) from None
    except AnalysisServiceError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI analysis is temporarily unavailable",
        ) from None
