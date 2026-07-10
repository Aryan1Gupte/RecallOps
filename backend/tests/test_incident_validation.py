import pytest
from pydantic import ValidationError

from recallops.schemas.incident import (
    IncidentCreate,
    IncidentEnvironment,
    IncidentStatus,
)


def test_incident_input_strips_surrounding_whitespace() -> None:
    incident = IncidentCreate(
        title="  Checkout latency  ",
        description="  Requests are timing out.  ",
        service="  checkout-api  ",
        environment="  production  ",
    )

    assert incident.title == "Checkout latency"
    assert incident.description == "Requests are timing out."
    assert incident.service == "checkout-api"
    assert incident.environment is IncidentEnvironment.PRODUCTION
    assert incident.status is IncidentStatus.OPEN


@pytest.mark.parametrize("field", ["title", "description", "service"])
def test_incident_input_rejects_blank_text(field: str) -> None:
    payload = {
        "title": "Checkout latency",
        "description": "Requests are timing out.",
        "service": "checkout-api",
        "environment": "production",
        field: "   ",
    }

    with pytest.raises(ValidationError):
        IncidentCreate(**payload)


def test_incident_input_rejects_description_over_max_length() -> None:
    payload = {
        "title": "Checkout latency",
        "description": "x" * 4001,
        "service": "checkout-api",
        "environment": "production",
    }

    with pytest.raises(ValidationError):
        IncidentCreate(**payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [("status", "closed"), ("environment", "staging")],
)
def test_incident_input_rejects_unknown_typed_values(field: str, value: str) -> None:
    payload = {
        "title": "Checkout latency",
        "description": "Requests are timing out.",
        "service": "checkout-api",
        "environment": "production",
        field: value,
    }

    with pytest.raises(ValidationError):
        IncidentCreate(**payload)
