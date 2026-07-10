from recallops.ai.embedding_text import (
    IncidentEmbeddingInput,
    build_incident_embedding_text,
)


def test_incident_embedding_text_is_deterministic_and_trimmed() -> None:
    incident = IncidentEmbeddingInput(
        title="  Checkout latency  ",
        description="  Requests are timing out.  ",
        service="  checkout-api  ",
        environment="  production  ",
        status="  investigating  ",
    )

    text = build_incident_embedding_text(incident)

    assert text == (
        "Title: Checkout latency\n"
        "Description: Requests are timing out.\n"
        "Service: checkout-api\n"
        "Environment: production\n"
        "Status: investigating"
    )
    assert "incident_id" not in text
    assert "created_at" not in text
    assert "updated_at" not in text
    assert "analysis" not in text.lower()
