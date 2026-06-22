from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Preferenza Connector"
    app_env: str = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    database_url: str = Field(default="sqlite+pysqlite:///./test.db", alias="DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    fernet_key: str = Field(default="", alias="FERNET_KEY")
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")
    default_tenant_id: str = Field(default="preferenza", alias="DEFAULT_TENANT_ID")
    sankhya_timeout_seconds: int = Field(default=30, alias="SANKHYA_TIMEOUT_SECONDS")
    sankhya_auth_timeout_seconds: int = Field(default=30, alias="SANKHYA_AUTH_TIMEOUT_SECONDS")
    sankhya_sandbox_base_url: str = Field(
        default="https://api.sandbox.sankhya.com.br", alias="SANKHYA_SANDBOX_BASE_URL"
    )
    sankhya_production_base_url: str = Field(default="https://api.sankhya.com.br", alias="SANKHYA_PRODUCTION_BASE_URL")
    sankhya_default_environment: str = Field(default="sandbox", alias="SANKHYA_DEFAULT_ENVIRONMENT")
    sankhya_read_test_entity: str = Field(default="", alias="SANKHYA_READ_TEST_ENTITY")
    sankhya_read_test_fields: str = Field(default="", alias="SANKHYA_READ_TEST_FIELDS")
    sankhya_read_test_limit: int = Field(default=1, ge=1, le=50, alias="SANKHYA_READ_TEST_LIMIT")
    celery_broker_url: str | None = Field(default=None, alias="CELERY_BROKER_URL")
    celery_result_backend: str | None = Field(default=None, alias="CELERY_RESULT_BACKEND")
    celery_task_always_eager: bool = Field(default=False, alias="CELERY_TASK_ALWAYS_EAGER")
    celery_task_eager_propagates: bool = Field(default=False, alias="CELERY_TASK_EAGER_PROPAGATES")
    celery_task_default_queue: str = Field(default="preferenza", alias="CELERY_TASK_DEFAULT_QUEUE")

    @property
    def parsed_cors_origins(self) -> list[str]:
        value = self.cors_origins.strip()
        if value == "*":
            return ["*"]
        return [item.strip() for item in value.split(",") if item.strip()]

    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url

    @property
    def sankhya_read_test_fields_list(self) -> list[str]:
        value = self.sankhya_read_test_fields.strip()
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
