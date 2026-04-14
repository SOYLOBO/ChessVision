"""
Engine Service – Configuration
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Stockfish binary path (override in .env or Docker ENV)
    STOCKFISH_PATH: str = "/usr/games/stockfish"

    # Default analysis depth when not provided by caller
    DEFAULT_DEPTH: int = 15

    # Default MultiPV lines
    DEFAULT_MULTI_PV: int = 3

    # CORS origins (comma-separated in env)
    CORS_ORIGINS: list[str] = ["*"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
