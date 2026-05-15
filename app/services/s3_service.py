from app.core.aws import s3_client
from app.core.config import settings


def build_input_key(user_type: str, request_id: str, filename: str = "input.wav") -> str:
    return f"uploads/{user_type}/{request_id}/{filename}"


def build_result_key(user_type: str, request_id: str) -> str:
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
