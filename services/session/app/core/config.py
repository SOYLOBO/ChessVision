from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    CONFIDENCE_THRESHOLD: float = 0.65
    CORS_ORIGINS: list[str] = ["*"]

    class Config:
        env_file = ".env"


settings = Settings()
