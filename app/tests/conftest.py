import logging
import os
from typing import AsyncGenerator

import debugpy
import httpx
import pytest
import pytest_asyncio
from beanie import init_beanie
from fastapi_mongo_base import models as base_mongo_models
from fastapi_mongo_base.utils.basic import get_all_subclasses
from server.config import Settings
from server.server import app as fastapi_app


@pytest.fixture(scope="session", autouse=True)
def setup_debugpy():
    if os.getenv("DEBUGPY", "False").lower() in ("true", "1", "yes"):
        debugpy.listen(("0.0.0.0", 3020))
        debugpy.wait_for_client()


@pytest.fixture(scope="session", autouse=True)
def settings():
    settings = Settings()
    settings.config_logger()
    return settings


@pytest.fixture(scope="session")
def mongo_client():
    from mongomock_motor import AsyncMongoMockClient

    mongo_client = AsyncMongoMockClient()
    yield mongo_client


# Async setup function to initialize the database with Beanie
async def init_db(mongo_client):
    database = mongo_client.get_database("test_db")
    await init_beanie(
        database=database,
        document_models=get_all_subclasses(base_mongo_models.BaseEntity),
    )


@pytest_asyncio.fixture(scope="session", autouse=True)
async def db(mongo_client):
    logging.info("Initializing database")
    await init_db(mongo_client)
    logging.info("Database initialized")
    yield
    logging.info("Cleaning up database")


@pytest_asyncio.fixture(scope="session")
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Fixture to provide an AsyncClient for FastAPI app."""

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=fastapi_app),
        base_url="http://test.ufaas.io",
        headers={"X-API-KEY": os.getenv("UFILES_API_KEY")},
    ) as ac:
        yield ac
