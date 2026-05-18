from fastapi import APIRouter, Depends, HTTPException

from app.core.config import settings
from app.core.security import get_optional_claims
from app.schemas.request_schema import PresignedUrlCreate
from app.services.request_service import build_request_context, build_storage_keys, make_request_id
from app.services.s3_service import create_upload_presigned_url
from app.services.user_service import fetch_user_by_id


router = APIRouter(prefix="/api/uploads", tags=["uploads"])


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


@router.post("/presigned-url")
def create_presigned_url(
    body: PresignedUrlCreate,
    claims: dict | None = Depends(get_optional_claims),
):
    user = resolve_current_user(claims)
    ctx = build_request_context(user)

    request_id = make_request_id()
    input_key, result_key = build_storage_keys(
        user_type=ctx["user_type"],
        request_id=request_id,
        original_file_name=body.original_file_name,
        tenant_id=ctx["tenant_id"],
    )

    upload_url = create_upload_presigned_url(input_key)

    return {
        "request_id": request_id,
        "upload_url": upload_url,
        "input_bucket": settings.input_bucket,
        "input_key": input_key,
        "result_bucket": settings.result_bucket,
        "result_key": result_key,
    }
