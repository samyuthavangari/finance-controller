from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore")

    app_name: str = "AI Finance Controller"
    api_prefix: str = "/api"
    environment: str = "development"
    database_url: str = "postgresql+psycopg2://finance:finance@localhost:5432/finance_controller"
    redis_url: str = "redis://localhost:6379/0"
    upstash_redis_rest_url: str = ""
    upstash_redis_rest_token: str = ""
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "finance_evidence"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    api_auth_token: str = "demo-token"
    auth_enabled: bool = True

    llm_provider: str = "gemini"
    llm_model: str = "gemini-2.5-flash"
    llm_vision_model: str = "gemini-2.5-flash"
    gemini_api_key: str = ""

    embedding_provider: str = "gemini"
    embedding_model: str = "text-embedding-004"

    ocr_provider: str = "huggingface"
    ocr_model: str = "PaddlePaddle/PaddleOCR-VL"
    hf_token: str = ""

    matching_model_path: str = str(ROOT / "data" / "synthetic" / "match_model.txt")
    data_dir: str = str(ROOT / "data")
    upload_dir: str = str(ROOT / "data" / "uploads")
    dataset_seed: int = 42

    log_level: str = "INFO"


settings = Settings()
