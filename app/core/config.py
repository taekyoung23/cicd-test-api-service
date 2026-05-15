from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "voice-auth-api-service"
    app_env: str = "local"
    api_prefix: str = "/api"

    aws_region: str = "ap-northeast-2"
    aws_profile: str | None = None

    input_bucket: str
    result_bucket: str

    free_queue_url: str | None = None
    paid_queue_url: str | None = None

    db_host: str | None = None
    db_port: int = 3306
    db_user: str | None = None
    db_password: str | None = None
    db_name: str | None = None

    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
