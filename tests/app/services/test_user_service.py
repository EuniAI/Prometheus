import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prometheus.app.entity.user import User
from prometheus.app.services.database_service import DatabaseService
from prometheus.app.services.user_service import UserService
from tests.test_utils.fixtures import postgres_container_fixture  # noqa: F401


@pytest.fixture
async def mock_database_service(postgres_container_fixture):  # noqa: F811
    service = DatabaseService(postgres_container_fixture.get_connection_url())
    await service.start()
    yield service
    await service.close()


async def test_create_superuser(mock_database_service):
    # Exercise
    service = UserService(mock_database_service)
    await service.create_superuser(
        "testuser", "test@gmail.com", "password123", github_token="gh_token"
    )

    # Verify
    async with AsyncSession(service.engine) as session:
        user = await session.get(User, 1)
        assert user is not None
        assert user.username == "testuser"
        assert user.email == "test@gmail.com"
        assert user.github_token == "gh_token"


async def test_login(mock_database_service):
    # Exercise
    service = UserService(mock_database_service)
    access_token = await service.login("testuser", "test@gmail.com", "password123")
    # Verify
    assert access_token is not None


async def test_set_github_token(mock_database_service):
    # Exercise
    service = UserService(mock_database_service)
    await service.set_github_token(1, "new_gh_token")
    # Verify
    async with AsyncSession(service.engine) as session:
        user = await session.get(User, 1)
        assert user is not None
        assert user.github_token == "new_gh_token"
