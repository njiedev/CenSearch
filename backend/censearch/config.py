"""Environment settings; relative paths always resolve against backend/."""

from pathlib import Path
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    data_dir: Path = Field(default=ROOT / "data", validation_alias="LIKENESS_DATA_DIR")
    models_dir: Path = Field(default=ROOT / "models", validation_alias="LIKENESS_MODELS_DIR")
    calibration_path: Path = Field(
        default=ROOT / "reports/calibration.json", validation_alias="LIKENESS_CALIBRATION_PATH"
    )
    frontend_dir: Path = Field(default=ROOT.parent / "frontend/dist", validation_alias="LIKENESS_FRONTEND_DIR")
    console_dir: Path = Field(default=ROOT / "demo-ui/dist", validation_alias="LIKENESS_CONSOLE_DIR")
    model_provider: str = "openai_compatible"
    openai_base_url: str = "https://ws.akamai-workshops.com/v1"
    openai_api_key: SecretStr = SecretStr("")
    chat_model: str = "hackathon-chat"
    model_max_tokens: int = Field(default=1024, ge=1, le=4096)
    obj_endpoint: str = ""
    obj_bucket: str = ""
    obj_access_key: SecretStr = SecretStr("")
    obj_secret_key: SecretStr = SecretStr("")
    allow_public_crawl: bool = False
    serpapi_api_key: SecretStr = Field(default=SecretStr(""), validation_alias="SERPAPI_API_KEY")
    facecheck_api_token: SecretStr = SecretStr("")
    discovery_max_queries: int = Field(default=8, ge=1, le=8)
    discovery_results_per_query: int = Field(default=10, ge=1, le=25)
    discovery_timeout: float = Field(default=90, gt=0, le=90)
    respect_robots: bool = False
    crawl_delay: float = Field(default=0.05, ge=0.01)
    crawl_request_budget: int = Field(default=400, ge=1, le=2000)
    mock_base_port: int = Field(default=8811, ge=1024, le=65527)
    allow_external_delivery: bool = Field(default=False, validation_alias="LIKENESS_ALLOW_EXTERNAL_DELIVERY")
    demo_clock: bool = Field(default=False, validation_alias="LIKENESS_DEMO_CLOCK")
    notice_interval: float = Field(default=172800, gt=0, validation_alias="LIKENESS_NOTICE_INTERVAL")
    scheduler_poll: float = Field(default=30, ge=0.1, validation_alias="LIKENESS_SCHEDULER_POLL")
    smtp_relay: str = Field(default="", validation_alias="LIKENESS_SMTP_RELAY")
    email_enabled: bool = Field(default=False, validation_alias="CENSEARCH_EMAIL_ENABLED")
    demo_resend: bool = Field(default=False, validation_alias="CENSEARCH_DEMO_RESEND")
    email_from: str = Field(default="", validation_alias="CENSEARCH_EMAIL_FROM")
    resend_api_key: SecretStr = SecretStr("")
    rdap_bootstrap: str = Field(default="", validation_alias="LIKENESS_RDAP_BOOTSTRAP")
    search_endpoint: str = Field(default="", validation_alias="LIKENESS_SEARCH_ENDPOINT")
    upload_limit_bytes: int = Field(default=20_000_000, ge=1024)

    @field_validator("data_dir", "models_dir", "calibration_path", "frontend_dir", "console_dir")
    @classmethod
    def absolute_path(cls, value: Path) -> Path:
        return value if value.is_absolute() else ROOT / value

    @property
    def model_configured(self) -> bool:
        return self.model_provider == "openai_compatible" and bool(self.openai_api_key.get_secret_value())

    @property
    def email_configured(self) -> bool:
        return bool(self.email_from and self.resend_api_key.get_secret_value())

    @property
    def object_storage_configured(self) -> bool:
        return all(
            (
                self.obj_endpoint,
                self.obj_bucket,
                self.obj_access_key.get_secret_value(),
                self.obj_secret_key.get_secret_value(),
            )
        )
