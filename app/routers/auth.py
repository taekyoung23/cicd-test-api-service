from fastapi import APIRouter, HTTPException

from app.core.security import create_access_token
from app.schemas.auth_schema import LoginRequest, SignupRequest, TokenResponse


router = APIRouter(prefix="/auth", tags=["auth"])


MOCK_USERS = {
    "free@test.com": {
        "password": "1234",
        "user_id": "user-free-001",
        "tenant_id": None,
        "tier_type": "FREE",
        "user_type": "free",
        "plan": "free",
        "queue_type": "FREE_QUEUE",
    },
    "paid@bank-a.com": {
        "password": "1234",
        "user_id": "user-paid-001",
        "tenant_id": "bank-a",
        "tier_type": "PAID",
        "user_type": "paid",
        "plan": "paid",
        "queue_type": "PAID_QUEUE",
    },
    "admin@securevoice.com": {
        "password": "1234",
        "user_id": "admin-001",
        "tenant_id": "securevoice",
        "tier_type": "ADMIN",
        "user_type": "admin",
        "plan": "paid",
        "queue_type": "ADMIN",
    },
}


@router.post("/login")
def login(body: LoginRequest):
    email = body.email.lower()
    user = MOCK_USERS.get(email)

    if not user or user["password"] != body.password:
        raise HTTPException(status_code=401, detail="invalid email or password")

    token = create_access_token(
        subject=user["user_id"],
        extra_claims={
            "email": email,
            "tier_type": user["tier_type"],
            "tenant_id": user["tenant_id"],
        },
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "email": email,
            "user_id": user["user_id"],
            "tenant_id": user["tenant_id"],
            "tier_type": user["tier_type"],
            "user_type": user["user_type"],
            "plan": user["plan"],
            "queue_type": user["queue_type"],
        },
    }


@router.post("/signup", response_model=TokenResponse)
def signup(body: SignupRequest):
    token = create_access_token(
        subject="user-free-001",
        extra_claims={
            "email": body.email.lower(),
            "tier_type": "FREE",
            "tenant_id": None,
        },
    )

    return {
        "access_token": token,
        "token_type": "bearer",
    }
