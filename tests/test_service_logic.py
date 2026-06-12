import os
from decimal import Decimal

import pytest

os.environ["APP_ENV"] = "ci"
os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
os.environ["INPUT_BUCKET"] = "ci-placeholder-input-bucket"
os.environ["RESULT_BUCKET"] = "ci-placeholder-result-bucket"

from app.services.request_service import (
    build_frontend_result,
    build_request_context,
    build_storage_keys,
    normalize_status_for_frontend,
)
from app.services.s3_service import safe_filename
from app.services.user_service import plan_from_user_type, queue_type_from_plan


@pytest.mark.parametrize(
    ("backend_status", "frontend_status"),
    [
        ("SUCCEEDED", "SUCCESS"),
        ("QUEUED", "QUEUED"),
        ("FAILED", "FAILED"),
    ],
)
def test_normalize_status_for_frontend(
    backend_status: str,
    frontend_status: str,
) -> None:
    assert normalize_status_for_frontend(backend_status) == frontend_status


@pytest.mark.parametrize(
    ("user_type", "expected_plan", "expected_queue"),
    [
        ("paid", "paid", "PAID_QUEUE"),
        ("free", "free", "FREE_QUEUE"),
        ("guest", "free", "FREE_QUEUE"),
    ],
)
def test_user_type_maps_to_expected_plan_and_queue(
    user_type: str,
    expected_plan: str,
    expected_queue: str,
) -> None:
    plan = plan_from_user_type(user_type)

    assert plan == expected_plan
    assert queue_type_from_plan(plan) == expected_queue


def test_build_request_context_for_guest() -> None:
    assert build_request_context(None) == {
        "user_id": None,
        "tenant_id": None,
        "user_type": "guest",
        "plan": "free",
    }


def test_build_request_context_for_paid_user() -> None:
    user = {
        "user_id": "user-123",
        "tenant_id": "tenant-456",
        "user_type": "paid",
    }

    assert build_request_context(user) == {
        "user_id": "user-123",
        "tenant_id": "tenant-456",
        "user_type": "paid",
        "plan": "paid",
    }


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("sample.wav", "sample.wav"),
        ("folder/sample.wav", "folder_sample.wav"),
        ("folder\\sample.wav", "folder_sample.wav"),
        ("   ", "input.wav"),
    ],
)
def test_safe_filename_removes_path_segments(filename: str, expected: str) -> None:
    assert safe_filename(filename) == expected


def test_build_storage_keys_for_tenant_user() -> None:
    input_key, result_key = build_storage_keys(
        user_type="paid",
        request_id="req-123",
        original_file_name="folder/sample.wav",
        tenant_id="tenant-456",
    )

    assert input_key == "uploads/tenants/tenant-456/paid/req-123/folder_sample.wav"
    assert result_key == "results/tenants/tenant-456/paid/req-123/result.json"


def test_build_frontend_result_converts_backend_values() -> None:
    result = build_frontend_result(
        {
            "request_id": "req-123",
            "status": "SUCCEEDED",
            "label": "fake",
            "confidence": Decimal("0.987"),
            "inference_time_sec": Decimal("1.234"),
            "model_version": None,
            "error_message": None,
        }
    )

    assert result == {
        "request_id": "req-123",
        "status": "SUCCESS",
        "result": "FAKE",
        "confidence": 0.987,
        "model_version": "Nes2Net-v1",
        "processing_time_ms": 1234,
        "error_message": None,
    }


def test_build_frontend_result_preserves_incomplete_result() -> None:
    result = build_frontend_result(
        {
            "request_id": "req-queued",
            "status": "QUEUED",
        }
    )

    assert result["status"] == "QUEUED"
    assert result["result"] is None
    assert result["confidence"] is None
    assert result["processing_time_ms"] is None
