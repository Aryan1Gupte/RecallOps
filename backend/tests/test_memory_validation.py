import pytest
from pydantic import ValidationError

from recallops.schemas.memory import MemoryCreate


def test_memory_create_strips_input_text() -> None:
    payload = MemoryCreate(
        memory_type=" resolution ",
        summary="  Cache flush fixed checkout  ",
        root_cause="   ",
        resolution=" Restart stale workers ",
    )

    assert payload.memory_type == "resolution"
    assert payload.summary == "Cache flush fixed checkout"
    assert payload.root_cause is None
    assert payload.resolution == "Restart stale workers"


def test_memory_create_rejects_invalid_type() -> None:
    with pytest.raises(ValidationError):
        MemoryCreate(memory_type="guess", summary="Useful detail")


def test_memory_create_rejects_client_controlled_fields() -> None:
    with pytest.raises(ValidationError):
        MemoryCreate(
            memory_type="resolution",
            summary="Useful detail",
            embedding=[0.0],
        )


def test_memory_create_rejects_blank_summary() -> None:
    with pytest.raises(ValidationError):
        MemoryCreate(memory_type="resolution", summary="   ")
