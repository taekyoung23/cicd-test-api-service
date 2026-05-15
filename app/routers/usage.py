from fastapi import APIRouter


router = APIRouter(prefix="/usage", tags=["usage"])


MOCK_USAGE = {
    "bank-a": {
        "tenant_id": "bank-a",
        "monthly_request_count": 1284,
        "success_count": 1241,
        "failed_count": 43,
        "avg_processing_time_ms": 18420,
    },
}


@router.get("/{tenant_id}")
def get_usage(tenant_id: str):
    return MOCK_USAGE.get(
        tenant_id,
        {
            "tenant_id": tenant_id,
            "monthly_request_count": 0,
            "success_count": 0,
            "failed_count": 0,
            "avg_processing_time_ms": 0,
        },
    )
