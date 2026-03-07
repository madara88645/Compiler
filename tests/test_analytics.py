from typing import Any, Dict

import pytest

from app.analytics import create_record_from_ir


class MockIRWithID:
    def __init__(self, id_val: str):
        self.id = id_val

    def __str__(self) -> str:
        return f"MockIRWithID(id={self.id})"


class MockIRWithoutID:
    def __str__(self) -> str:
        return "MockIRWithoutID()"


def test_create_record_from_ir_with_id():
    """Test create_record_from_ir when the IR object has an id."""
    ir = MockIRWithID("test-id-123")
    record = create_record_from_ir(ir)

    assert isinstance(record, dict)
    assert record["id"] == "test-id-123"
    assert record["timestamp"] == "2024-01-01T00:00:00"
    assert record["prompt"] == "MockIRWithID(id=test-id-123)"
    assert record["metrics"] == {}


def test_create_record_from_ir_without_id():
    """Test create_record_from_ir when the IR object does not have an id."""
    ir = MockIRWithoutID()
    record = create_record_from_ir(ir)

    assert isinstance(record, dict)
    assert record["id"] == "unknown"
    assert record["timestamp"] == "2024-01-01T00:00:00"
    assert record["prompt"] == "MockIRWithoutID()"
    assert record["metrics"] == {}


def test_create_record_from_ir_with_additional_args():
    """Test create_record_from_ir handles additional args and kwargs safely."""
    ir = MockIRWithID("test-id-456")

    # Should not raise an error despite extra args
    record = create_record_from_ir(ir, "extra_arg", extra_kwarg="value")

    assert isinstance(record, dict)
    assert record["id"] == "test-id-456"
    assert record["timestamp"] == "2024-01-01T00:00:00"
    assert record["prompt"] == "MockIRWithID(id=test-id-456)"
    assert record["metrics"] == {}
