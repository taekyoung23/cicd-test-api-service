from typing import Literal

from pydantic import BaseModel, Field


UserType = Literal["guest", "free", "paid"]
Plan = Literal["free", "paid"]
RequestStatus = Literal["QUEUED", "PROCESSING", "SUCCEEDED", "FAILED"]


class PresignedUrlCreate(BaseModel):
    user_id: str | None = None
    user_type: UserType = "guest"
    filename: str = "input.wav"


class PresignedUrlResult(BaseModel):
    request_id: str
    upload_url: str
    input_bucket: str
    input_key: str
    result_bucket: str
    result_key: str


class InferenceRequestCreate(BaseModel):
    request_id: str
    user_id: str | None = None
    user_type: UserType = "guest"
    plan: Plan = "free"

    input_bucket: str
    input_key: str
    result_bucket: str
    result_key: str


class InferenceRequestRow(BaseModel):
    request_id: str
    user_id: str | None = None
    user_type: UserType
    plan: Plan
    input_bucket: str
    input_key: str
    result_bucket: str | None = None
    result_key: str | None = None
    status: RequestStatus

    label: str | None = None
    confidence: float | None = None
    fake_prob: float | None = None
    real_prob: float | None = None
    model_name: str | None = None
    model_version: str | None = None
    inference_time_sec: float | None = None
    error_message: str | None = None
