import uuid
from decimal import Decimal

import boto3
from fastapi import UploadFile

from app.core.config import settings
from app.db.database import get_connection
from app.services.s3_service import build_input_key, build_result_key
from app.services.sqs_service import send_inference_message
from app.services.user_service import plan_from_user_type


def make_request_id() -> str:
    return f"req-{uuid.uuid4().hex}"


def to_float(value):
    if isinstance(value, Decimal):
        return float(value)
    return value


def normalize_status_for_frontend(status: str) -> str:
    return "SUCCESS" if status == "SUCCEEDED" else status


def build_request_context(user: dict | None) -> dict:
    if user is None:
        return {
            "user_id": None,
            "tenant_id": None,
            "user_type": "guest",
            "plan": "free",
        }

    user_type = user["user_type"]
    plan = plan_from_user_type(user_type)

    return {
        "user_id": user["user_id"],
        "tenant_id": user["tenant_id"],
        "user_type": user_type,
        "plan": plan,
    }


def build_storage_keys(
    user_type: str,
    request_id: str,
    original_file_name: str,
    tenant_id: str | None,
) -> tuple[str, str]:
    input_key = build_input_key(
        user_type=user_type,
        request_id=request_id,
        filename=original_file_name,
        tenant_id=tenant_id,
    )

    result_key = build_result_key(
        user_type=user_type,
        request_id=request_id,
        tenant_id=tenant_id,
    )

    return input_key, result_key

def upload_input_audio(uploaded_file: UploadFile, bucket: str, key: str) -> None:
    s3 = boto3.client("s3", region_name=settings.aws_region)

    uploaded_file.file.seek(0)

    s3.upload_fileobj(
        uploaded_file.file,
        bucket,
        key,
        ExtraArgs={
            "ContentType": uploaded_file.content_type or "audio/wav"
        },
    )

def insert_inference_request(row: dict) -> None:
    sql = """
    INSERT INTO inference_requests (
      request_id,
      user_id,
      tenant_id,
      user_type,
      plan,
      input_bucket,
      input_key,
      result_bucket,
      result_key,
      status
    )
    VALUES (
      %(request_id)s,
      %(user_id)s,
      %(tenant_id)s,
      %(user_type)s,
      %(plan)s,
      %(input_bucket)s,
      %(input_key)s,
      %(result_bucket)s,
      %(result_key)s,
      'QUEUED'
    )
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, row)


def create_and_enqueue_request(
    uploaded_file: UploadFile,
    original_file_name: str,
    user: dict | None,
) -> dict:
    request_id = make_request_id()
    ctx = build_request_context(user)

    input_key, result_key = build_storage_keys(
        user_type=ctx["user_type"],
        request_id=request_id,
        original_file_name=original_file_name,
        tenant_id=ctx["tenant_id"],
    )

    row = {
        "request_id": request_id,
        "user_id": ctx["user_id"],
        "tenant_id": ctx["tenant_id"],
        "user_type": ctx["user_type"],
        "plan": ctx["plan"],
        "input_bucket": settings.input_bucket,
        "input_key": input_key,
        "result_bucket": settings.result_bucket,
        "result_key": result_key,
    }

    upload_input_audio(
        uploaded_file=uploaded_file,
        bucket=settings.input_bucket,
        key=input_key,
    )

    insert_inference_request(row)
    send_inference_message(row)

    queue_type = "PAID_QUEUE" if row["plan"] == "paid" else "FREE_QUEUE"

    return {
        "request_id": request_id,
        "queue_type": queue_type,
        "created_at": find_inference_request(request_id)["created_at"],
    }


def find_inference_request(request_id: str) -> dict | None:
    sql = """
    SELECT *
    FROM inference_requests
    WHERE request_id = %s
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (request_id,))
            return cur.fetchone()


def find_inference_requests(user_id: str, limit: int = 20) -> list[dict]:
    sql = """
    SELECT *
    FROM inference_requests
    WHERE user_id = %s
    ORDER BY created_at DESC
    LIMIT %s
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (user_id, limit))
            return cur.fetchall()


def build_frontend_result(row: dict) -> dict:
    confidence = to_float(row.get("confidence"))
    inference_time_sec = to_float(row.get("inference_time_sec"))

    processing_time_ms = None
    if inference_time_sec is not None:
        processing_time_ms = int(inference_time_sec * 1000)

    label = row.get("label")
    result = label.upper() if label else None

    return {
        "request_id": row["request_id"],
        "status": normalize_status_for_frontend(row["status"]),
        "result": result,
        "confidence": confidence,
        "model_version": row.get("model_version") or "Nes2Net-v1",
        "processing_time_ms": processing_time_ms,
        "error_message": row.get("error_message"),
    }
