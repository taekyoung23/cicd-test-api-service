from pydantic import BaseModel, EmailStr


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str = "무료 사용자"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    user_id: str | None
    email: str | None = None
    display_name: str
    user_type: str
    tenant_id: str | None = None
    queue_type: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
