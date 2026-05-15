from fastapi import APIRouter, HTTPException, Query

from app.schemas.request_schema import InferenceRequestCreate
from app.services.request_service import (
    enqueue_inference_request,
    find_inference_request,
    find_inference_requests,
)


router = APIRouter(prefix="/requests", tags=["requests"])


@router.post("")
def create_request(body: InferenceRequestCreate):
    return enqueue_inference_request(body.model_dump())


@router.get("/{request_id}")
def get_request(request_id: str):
    row = find_inference_request(request_id)

    if not row:
        raise HTTPException(status_code=404, detail="request not found")

    return row


@router.get("")
def list_requests(
    user_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
):
    return find_inference_requests(user_id=user_id, limit=limit)
