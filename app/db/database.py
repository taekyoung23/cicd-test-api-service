import pymysql
from pymysql.connections import Connection

from app.core.config import settings


def get_connection() -> Connection:
    if not all([
        settings.db_host,
        settings.db_user,
        settings.db_password,
        settings.db_name,
    ]):
        raise RuntimeError("DB environment variables are not configured")

    return pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )
