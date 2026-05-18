import uuid

from app.core.security import hash_password
from app.db.database import get_connection


def make_user_id() -> str:
    return f"user-{uuid.uuid4().hex[:12]}"


def fetch_user_by_email(email: str) -> dict | None:
    sql = """
    SELECT
      u.user_id,
      u.email,
      u.password_hash,
      u.display_name,
      u.user_type,
      u.tenant_id,
      t.plan AS tenant_plan
    FROM users u
    LEFT JOIN tenants t
      ON u.tenant_id = t.tenant_id
    WHERE u.email = %s
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (email,))
            return cur.fetchone()


def fetch_user_by_id(user_id: str) -> dict | None:
    sql = """
    SELECT
      u.user_id,
      u.email,
      u.password_hash,
      u.display_name,
      u.user_type,
      u.tenant_id,
      t.plan AS tenant_plan
    FROM users u
    LEFT JOIN tenants t
      ON u.tenant_id = t.tenant_id
    WHERE u.user_id = %s
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (user_id,))
            return cur.fetchone()


def create_free_user(email: str, password: str, display_name: str) -> dict:
    user_id = make_user_id()
    password_hash = hash_password(password)

    sql = """
    INSERT INTO users (
      user_id,
      email,
      password_hash,
      display_name,
      user_type,
      tenant_id
    )
    VALUES (%s, %s, %s, %s, 'free', NULL)
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    user_id,
                    email,
                    password_hash,
                    display_name,
                ),
            )

    user = fetch_user_by_id(user_id)
    if user is None:
        raise RuntimeError("created user not found")

    return user


def plan_from_user_type(user_type: str) -> str:
    return "paid" if user_type == "paid" else "free"


def queue_type_from_plan(plan: str) -> str:
    return "PAID_QUEUE" if plan == "paid" else "FREE_QUEUE"


def build_user_response(user: dict, access_token: str | None = None) -> dict:
    plan = plan_from_user_type(user["user_type"])

    response = {
        "user_id": user["user_id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "user_type": user["user_type"],
        "tenant_id": user["tenant_id"],
        "plan": plan,
        "queue_type": queue_type_from_plan(plan),
    }

    if access_token:
        response["access_token"] = access_token
        response["token_type"] = "bearer"

    return response


def build_guest_user() -> dict:
    return {
        "user_id": None,
        "email": None,
        "display_name": "비로그인 체험 사용자",
        "user_type": "guest",
        "tenant_id": None,
        "plan": "free",
        "queue_type": "FREE_QUEUE",
    }
