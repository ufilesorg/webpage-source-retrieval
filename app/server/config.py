"""FastAPI server configuration."""

import dataclasses
import os
from pathlib import Path

import dotenv
from fastapi_mongo_base.core import config

dotenv.load_dotenv()


@dataclasses.dataclass
class Settings(config.Settings):
    base_dir: Path = Path(__file__).resolve().parent.parent
    base_path: str = "/v1/apps/webpage"

    selenium_remote_url: str = os.getenv("SELENIUM_REMOTE_URL", "http://localhost:4444")
    selenium_loading_time: int = 5
    httpx_timeout: int = 10
    browser_timeout: int = 20

    GSEARCH_API_KEY: str = os.getenv("GSEARCH_API_KEY")
    GSEARCH_CX: str = os.getenv("GSEARCH_CX")
