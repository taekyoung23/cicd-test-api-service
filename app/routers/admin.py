from fastapi import APIRouter


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/metrics")
def get_admin_metrics():
    return {
        "freeQueueLength": 14,
        "paidQueueLength": 3,
        "freeWorkerStatus": "RUNNING 2/2",
        "paidWorkerStatus": "RUNNING 4/4",
        "dlqMessages": 2,
        "api5xxErrors": 1,
        "recentFailures": [
            {
                "request_id": "SVG-20260515-F010",
                "queue_type": "FREE_QUEUE",
                "reason": "Unsupported audio codec",
            },
            {
                "request_id": "SVG-20260515-P004",
                "queue_type": "PAID_QUEUE",
                "reason": "Model timeout",
            },
        ],
    }
