import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.database import get_connection
from app.schemas.auth_schema import LoginRequest, SignupRequest
from app.services.sqs_service import send_inference_message


router = APIRouter(prefix="/api", tags=["frontend-compat"])


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_user_id() -> str:
    return f"user-{uuid.uuid4().hex[:12]}"


def make_request_id() -> str:
    return f"req-{uuid.uuid4().hex}"


def queue_type_from_user_type(user_type: str) -> str:
    if user_type == "paid":
        return "PAID_QUEUE"
    if user_type == "admin":
        return "ADMIN"
    return "FREE_QUEUE"


def plan_from_user_type(user_type: str) -> str:
    return "paid" if user_type == "paid" else "free"


def frontend_display_name(row: dict) -> str:
    if row["user_type"] == "paid":
        return "유료 고객"
    if row["user_type"] == "admin":
        return "관리자"
    return row["display_name"]


def build_user_response(row: dict) -> dict:
    return {
        "user_id": row["user_id"],
        "email": row["email"],
        "display_name": frontend_display_name(row),
        "user_type": row["user_type"],
        "tenant_id": row.get("tenant_id"),
        "queue_type": queue_type_from_user_type(row["user_type"]),
    }


def fetch_user_by_email(email: str) -> dict | None:
    sql = """
    SELECT
      user_id,
      email,
      password_hash,
      display_name,
      user_type,
      tenant_id
    FROM users
    WHERE email = %s
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (email,))
            return cur.fetchone()


@router.post("/guest")
def guest_session():
    return {
        "user_id": None,
        "email": None,
        "display_name": "비로그인 체험 사용자",
        "user_type": "guest",
        "tenant_id": None,
        "queue_type": "FREE_QUEUE",
    }


@router.post("/signup")
def signup(body: SignupRequest):
    email = body.email.lower().strip()
    exists = fetch_user_by_email(email)

    if exists:
        raise HTTPException(status_code=409, detail="already registered email")

    user_id = make_user_id()
    password_hash = hash_password(body.password)

    sql = """
    INSERT INTO users (
      user_id,
      email,
      password_hash,
      display_name,
      user_type,
      tenant_id
    )
    VALUES (%s, %s, %s, %s, 'free', NULL)
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    user_id,
                    email,
                    password_hash,
                    body.display_name or "무료 사용자",
                ),
            )

    user = fetch_user_by_email(email)
    return build_user_response(user)


@router.post("/login")
def login(body: LoginRequest):
    email = body.email.lower().strip()
    user = fetch_user_by_email(email)

    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="invalid email or password")

    token = create_access_token(
        subject=user["user_id"],
        extra_claims={
            "email": user["email"],
            "user_type": user["user_type"],
            "tenant_id": user["tenant_id"],
        },
    )

    response = build_user_response(user)
    response["access_token"] = token
    response["token_type"] = "bearer"

    return response


@router.post("/analysis/request")
def create_analysis_request(body: dict):
    user = body.get("user") or {}
    original_file_name = body.get("original_file_name") or "input.wav"

    request_id = make_request_id()

    user_id = user.get("user_id")
    user_type = user.get("user_type") or "guest"
    tenant_id = user.get("tenant_id")
    plan = plan_from_user_type(user_type)

    normalized_user_type = user_type if user_type in ("guest", "free", "paid") else "free"

    input_key = f"uploads/{normalized_user_type}/{request_id}/{original_file_name}"
    result_key = f"results/{normalized_user_type}/{request_id}/result.json"

    row = {
        "request_id": request_id,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "user_type": normalized_user_type,
        "plan": plan,
        "input_bucket": settings.input_bucket,
        "input_key": input_key,
        "result_bucket": settings.result_bucket,
        "result_key": result_key,
    }

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

    try:
        send_inference_message(row)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"SQS enqueue failed: {exc}")

    return {
        "request_id": request_id,
        "queue_type": queue_type_from_user_type(normalized_user_type),
        "created_at": now_iso(),
    }


@router.get("/analysis/{request_id}/result")
def get_analysis_result(request_id: str):
    sql = """
    SELECT
      request_id,
      status,
      label,
      confidence,
      model_version,
      inference_time_sec,
      error_message
    FROM inference_requests
    WHERE request_id = %s
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (request_id,))
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="request not found")

    status = row["status"]
    frontend_status = "SUCCESS" if status == "SUCCEEDED" else status

    result = None
    if row["label"]:
        result = str(row["label"]).upper()

    confidence = row["confidence"]
    if isinstance(confidence, Decimal):
        confidence = float(confidence)

    inference_time_sec = row["inference_time_sec"]
    if isinstance(inference_time_sec, Decimal):
        inference_time_sec = float(inference_time_sec)

    processing_time_ms = None
    if inference_time_sec is not None:
        processing_time_ms = int(inference_time_sec * 1000)

    return {
        "request_id": row["request_id"],
        "status": frontend_status,
        "result": result,
        "confidence": confidence,
        "model_version": row["model_version"] or "Nes2Net-v1",
        "processing_time_ms": processing_time_ms,
        "error_message": row["error_message"],
    }


@router.get("/usage/{tenant_id}")
def get_usage(tenant_id: str):
    sql = """
    SELECT
      t.tenant_id,
      t.tenant_display_name,
      COUNT(r.request_id) AS monthly_request_count,
      COALESCE(SUM(r.status = 'SUCCEEDED'), 0) AS success_count,
      COALESCE(SUM(r.status = 'FAILED'), 0) AS failed_count,
      COALESCE(AVG(r.inference_time_sec), 0) AS average_inference_time_sec
    FROM tenants t
    LEFT JOIN inference_requests r
      ON t.tenant_id = r.tenant_id
      AND r.created_at >= DATE_FORMAT(NOW(), '%%Y-%%m-01')
    WHERE t.tenant_id = %s
    GROUP BY t.tenant_id, t.tenant_display_name
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (tenant_id,))
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="tenant not found")

    avg_sec = row["average_inference_time_sec"]
    if isinstance(avg_sec, Decimal):
        avg_sec = float(avg_sec)

    return {
        "tenant_id": row["tenant_id"],
        "tenant_display_name": row["tenant_display_name"],
        "monthly_request_count": int(row["monthly_request_count"]),
        "success_count": int(row["success_count"]),
        "failed_count": int(row["failed_count"]),
        "average_processing_time_ms": int(avg_sec * 1000),
    }
