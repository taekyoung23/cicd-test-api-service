from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File

from app.core.security import get_optional_claims, get_required_claims
from app.services.request_service import (
    build_frontend_result,
    create_and_enqueue_request,
    find_inference_request,
    find_inference_requests,
)
from app.services.user_service import fetch_user_by_id


router = APIRouter(prefix="/api", tags=["requests"])


def resolve_current_user(claims: dict | None) -> dict | None:
    if claims is None:
        return None

    user_id = claims.get("sub") or claims.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="invalid token")

    user = fetch_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="user not found")

    return user


@router.post("/analysis/request")
def create_analysis_request(
    file: UploadFile = File(...),
    claims: dict | None = Depends(get_optional_claims),
):
    user = resolve_current_user(claims)

    return create_and_enqueue_request(
        uploaded_file=file,
        original_file_name=file.filename,
        user=user,
    )


@router.get("/analysis/{request_id}/result")
def get_analysis_result(request_id: str):
    row = find_inference_request(request_id)

    if not row:
        raise HTTPException(status_code=404, detail="request not found")

    return build_frontend_result(row)


@router.get("/requests")
def list_my_requests(
    limit: int = Query(default=20, ge=1, le=100),
    claims: dict = Depends(get_required_claims),
):
    user_id = claims.get("sub") or claims.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="invalid token")

    return find_inference_requests(user_id=user_id, limit=limit)


@router.get("/requests/{request_id}")
def get_request(request_id: str):
    row = find_inference_request(request_id)

    if not row:
        raise HTTPException(status_code=404, detail="request not found")

    return row