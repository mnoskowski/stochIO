import os
from collections.abc import AsyncIterator
from urllib.parse import urlparse

import pytest
from httpx import ASGITransport, AsyncClient

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://dev:dev@localhost:5433/stochio_test"
)

suffix = urlparse(TEST_DATABASE_URL).path.lstrip("/")
if not suffix.endswith("_test"):
    raise RuntimeError("Database URL should end with '_test'")

os.environ["DATABASE_URL"] = TEST_DATABASE_URL

# Settings() reads env at import (app imports it) thus app must be imported after
from app.main import app  # noqa: E402


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
