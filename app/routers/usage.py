from decimal import Decimal

from fastapi import APIRouter, HTTPException

from app.db.database import get_connection


router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.get("/{tenant_id}")
def get_usage(tenant_id: str):
    sql = """
    SELECT
      t.tenant_id,
      t.tenant_display_name,
      COUNT(r.request_id) AS monthly_request_count,
      COALESCE(SUM(r.status = 'SUCCEEDED'), 0) AS success_count,
      COALESCE(SUM(r.status = 'FAILED'), 0) AS failed_count,
      COALESCE(AVG(r.inference_time_sec), 0) AS avg_inference_time_sec
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

    avg_sec = row["avg_inference_time_sec"]
    if isinstance(avg_sec, Decimal):
        avg_sec = float(avg_sec)

    return {
        "tenant_id": row["tenant_id"],
        "tenant_display_name": row["tenant_display_name"],
        "monthly_request_count": int(row["monthly_request_count"]),
        "success_count": int(row["success_count"]),
        "failed_count": int(row["failed_count"]),
        "avg_processing_time_ms": int(avg_sec * 1000),
        "average_processing_time_ms": int(avg_sec * 1000),
    }
