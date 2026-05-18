from typing import Literal

from pydantic import BaseModel


UserType = Literal["guest", "free", "paid"]
Plan = Literal["free", "paid"]
RequestStatus = Literal["QUEUED", "PROCESSING", "SUCCEEDED", "FAILED"]


class AnalysisRequestCreate(BaseModel):
    original_file_name: str


class PresignedUrlCreate(BaseModel):
    original_file_name: str


class PresignedUrlResult(BaseModel):
    request_id: str
    upload_url: str
    input_bucket: str
    input_key: str
    result_bucket: str
    result_key: str


class InferenceRequestCreate(BaseModel):
    request_id: str
    input_bucket: str
    input_key: str
    result_bucket: str
    result_key: str


class InferenceRequestRow(BaseModel):
    request_id: str
    user_id: str | None
    tenant_id: str | None
    user_type: UserType
    plan: Plan

    input_bucket: str
    input_key: str
    result_bucket: str | None
    result_key: str | None

    status: RequestStatus

    label: str | None = None
    confidence: float | None = None
    fake_prob: float | None = None
    real_prob: float | None = None

    model_name: str | None = None
    model_version: str | None = None
    inference_time_sec: float | None = None
    error_message: str | None = None
