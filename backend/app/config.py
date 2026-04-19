from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "스크린골프 운영 서비스"
    database_url: str = Field(default="sqlite:///./screen_golf.db", alias="DATABASE_URL")
    cors_origins: str = Field(default="http://localhost:5173,http://localhost:8080", alias="CORS_ORIGINS")
    operator_name: str = Field(default="관리자", alias="OPERATOR_NAME")
    ncp_sms_service_id: str | None = Field(default=None, alias="NCP_SMS_SERVICE_ID")
    ncp_access_key: str | None = Field(default=None, alias="NCP_ACCESS_KEY")
    ncp_secret_key: str | None = Field(default=None, alias="NCP_SECRET_KEY")
    ncp_sms_from_number: str | None = Field(default=None, alias="NCP_SMS_FROM_NUMBER")
    ncp_sms_billing_keywords: str | None = Field(default=None, alias="NCP_SMS_BILLING_KEYWORDS")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def sms_provider_configured(self) -> bool:
        return all(
            [
                (self.ncp_sms_service_id or "").strip(),
                (self.ncp_access_key or "").strip(),
                (self.ncp_secret_key or "").strip(),
                (self.ncp_sms_from_number or "").strip(),
            ]
        )

    @property
    def sms_billing_keyword_list(self) -> list[str]:
        raw_value = self.ncp_sms_billing_keywords or "simple & easy notification service,sens,sms"
        return [item.strip() for item in raw_value.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
