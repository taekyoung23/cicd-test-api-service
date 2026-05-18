from app.core.aws import s3_client
from app.core.config import settings


def safe_filename(filename: str) -> str:
    return filename.replace("/", "_").replace("\\", "_").strip() or "input.wav"


def build_input_key(
    user_type: str,
    request_id: str,
    filename: str,
    tenant_id: str | None = None,
) -> str:
    filename = safe_filename(filename)

    if tenant_id:
        return f"uploads/tenants/{tenant_id}/{user_type}/{request_id}/{filename}"

    return f"uploads/{user_type}/{request_id}/{filename}"


def build_result_key(
    user_type: str,
    request_id: str,
    tenant_id: str | None = None,
) -> str:
    if tenant_id:
        return f"results/tenants/{tenant_id}/{user_type}/{request_id}/result.json"

    return f"results/{user_type}/{request_id}/result.json"


def create_upload_presigned_url(
    input_key: str,
    content_type: str = "audio/wav",
    expires_in: int = 900,
) -> str:
    return s3_client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.input_bucket,
            "Key": input_key,
            "ContentType": content_type,
        },
        ExpiresIn=expires_in,
    )
