from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "staging", "production"] = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    secret_key: str = "dev-only-change-me"
    database_url: str = "postgresql+psycopg://bgm:bgm_dev_password@127.0.0.1:5432/bgm_travels"
    test_database_url: str = "postgresql+psycopg://bgm:bgm_dev_password@127.0.0.1:5433/bgm_travels_test"
    cors_origins: str = "http://localhost:3000"
    public_app_url: str = "http://localhost:3000"
    hold_ttl_minutes: int = Field(default=10, ge=1, le=60)
    bus_turnaround_minutes: int = Field(default=180, ge=0)
    cancellation_cutoff_minutes: int = Field(default=60, ge=0)
    offline_payment_methods: list[str] = ["cash", "upi", "bank_transfer"]
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_api_version: str = "v23.0"
    whatsapp_template_name: str = "bgm_booking_update"
    whatsapp_template_language: str = "en"
    notification_max_attempts: int = Field(default=5, ge=1, le=20)

    admin_email: str = "admin@bgmtravels.in"
    admin_password: str = "Admin123"
    admin_name: str = "BGM Operator"

    payment_provider: Literal["razorpay", "fake"] = "fake"
    razorpay_key_id: str = "rzp_test_placeholder"
    razorpay_key_secret: str = "replace-me"
    razorpay_webhook_secret: str = "replace-me"
    payments_live_enabled: bool = False

    brand_name: str = "BGM Travels"

    @field_validator("cors_origins")
    @classmethod
    def strip_origins(cls, value: str) -> str:
        return value.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
