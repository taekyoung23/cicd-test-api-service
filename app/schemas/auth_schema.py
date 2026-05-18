from pydantic import BaseModel, EmailStr


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    user_id: str | None
    email: str | None = None
    display_name: str
    user_type: str
    tenant_id: str | None = None
    plan: str
    queue_type: str
    access_token: str | None = None
    token_type: str | None = None
