from fastapi import APIRouter

from app.schemas.request_schema import PresignedUrlCreate, PresignedUrlResult
from app.services.request_service import prepare_presigned_upload


router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/presigned-url", response_model=PresignedUrlResult)
def create_presigned_url(body: PresignedUrlCreate):
    return prepare_presigned_upload(
        user_id=body.user_id,
        user_type=body.user_type,
        filename=body.filename,
    )
