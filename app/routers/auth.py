from fastapi import APIRouter, HTTPException

from app.core.security import create_access_token, verify_password
from app.schemas.auth_schema import LoginRequest, SignupRequest
from app.services.user_service import (
    build_guest_user,
    build_user_response,
    create_free_user,
    fetch_user_by_email,
    plan_from_user_type,
)


router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/guest")
def guest_session():
    return build_guest_user()


@router.post("/signup")
def signup(body: SignupRequest):
    email = body.email.lower().strip()

    exists = fetch_user_by_email(email)
    if exists:
        raise HTTPException(status_code=409, detail="already registered email")

    user = create_free_user(
        email=email,
        password=body.password,
        display_name=body.display_name,
    )

    plan = plan_from_user_type(user["user_type"])

    token = create_access_token(
        subject=user["user_id"],
        extra_claims={
            "user_id": user["user_id"],
            "email": user["email"],
            "user_type": user["user_type"],
            "tenant_id": user["tenant_id"],
            "plan": plan,
        },
    )

    return build_user_response(user, access_token=token)


@router.post("/login")
def login(body: LoginRequest):
    email = body.email.lower().strip()
    user = fetch_user_by_email(email)

    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="invalid email or password")

    plan = plan_from_user_type(user["user_type"])

    token = create_access_token(
        subject=user["user_id"],
        extra_claims={
            "user_id": user["user_id"],
            "email": user["email"],
            "user_type": user["user_type"],
            "tenant_id": user["tenant_id"],
            "plan": plan,
        },
    )

    return build_user_response(user, access_token=token)
