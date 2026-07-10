from recallops.ai.memory_embedding_text import build_memory_embedding_text


class LinkedIncident:
    title = " Checkout latency "
    service = " checkout-api "
    environment = " production "


def test_build_memory_embedding_text_without_incident() -> None:
    text = build_memory_embedding_text(
        memory_type=" resolution ",
        summary=" Cache flush restored checkout ",
        root_cause=None,
        resolution=" Restarted the stale workers ",
    )

    assert text == (
        "Memory Type: resolution\n"
        "Summary: Cache flush restored checkout\n"
        "Root Cause: Not provided\n"
        "Resolution: Restarted the stale workers"
    )


def test_build_memory_embedding_text_with_safe_incident_context() -> None:
    text = build_memory_embedding_text(
        memory_type="failed_action",
        summary="Rollback did not reduce latency",
        root_cause="Database pool saturation",
        resolution=None,
        incident=LinkedIncident(),
    )

    assert text == (
        "Memory Type: failed_action\n"
        "Summary: Rollback did not reduce latency\n"
        "Root Cause: Database pool saturation\n"
        "Resolution: Not provided\n"
        "Incident Title: Checkout latency\n"
        "Incident Service: checkout-api\n"
        "Incident Environment: production"
    )
    assert "Incident ID" not in text
    assert "Created" not in text
