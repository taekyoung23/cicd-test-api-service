from fastapi import APIRouter

from app.db.database import get_connection


router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/metrics")
def get_admin_metrics():
    failed_sql = """
    SELECT
      request_id,
      user_type,
      plan,
      error_message,
      updated_at
    FROM inference_requests
    WHERE status = 'FAILED'
    ORDER BY updated_at DESC
    LIMIT 10
    """

    count_sql = """
    SELECT
      COALESCE(SUM(status = 'FAILED'), 0) AS failed_count,
      COALESCE(SUM(status = 'SUCCEEDED'), 0) AS success_count,
      COUNT(*) AS total_count
    FROM inference_requests
    WHERE created_at >= DATE_FORMAT(NOW(), '%%Y-%%m-01')
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(failed_sql)
            failures = cur.fetchall()

            cur.execute(count_sql)
            counts = cur.fetchone()

    return {
        "monthlyTotalRequests": int(counts["total_count"]),
        "monthlySuccessCount": int(counts["success_count"]),
        "monthlyFailedCount": int(counts["failed_count"]),
        "recentFailures": [
            {
                "request_id": item["request_id"],
                "queue_type": "PAID_QUEUE" if item["plan"] == "paid" else "FREE_QUEUE",
                "reason": item["error_message"] or "unknown error",
                "updated_at": item["updated_at"],
            }
            for item in failures
        ],
    }
