import uuid

from app.core.config import settings
from app.db.database import get_connection
from app.services.s3_service import (
    build_input_key,
    build_result_key,
    create_upload_presigned_url,
)
from app.services.sqs_service import send_inference_message


def create_request_id() -> str:
    return f"req-{uuid.uuid4().hex}"


def normalize_plan(user_type: str) -> str:
    return "paid" if user_type == "paid" else "free"


def prepare_presigned_upload(user_id: str | None, user_type: str, filename: str) -> dict:
    request_id = create_request_id()

    input_key = build_input_key(user_type, request_id, filename)
    result_key = build_result_key(user_type, request_id)
    upload_url = create_upload_presigned_url(input_key)

    return {
        "request_id": request_id,
        "upload_url": upload_url,
        "input_bucket": settings.input_bucket,
        "input_key": input_key,
        "result_bucket": settings.result_bucket,
        "result_key": result_key,
    }


def insert_inference_request(row: dict) -> None:
    sql = """
    INSERT INTO inference_requests (
        request_id,
        user_id,
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


def enqueue_inference_request(row: dict) -> dict:
    row["plan"] = normalize_plan(row["user_type"])

    insert_inference_request(row)
    send_inference_message(row)

    return {
        "request_id": row["request_id"],
        "status": "QUEUED",
        "plan": row["plan"],
    }


def find_inference_request(request_id: str) -> dict | None:
    sql = "SELECT * FROM inference_requests WHERE request_id = %s"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (request_id,))
            return cur.fetchone()


def find_inference_requests(user_id: str | None = None, limit: int = 20) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            if user_id:
                cur.execute(
                    """
                    SELECT *
                    FROM inference_requests
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (user_id, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT *
                    FROM inference_requests
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )

            return cur.fetchall()
