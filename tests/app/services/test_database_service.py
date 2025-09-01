import pytest

from prometheus.app.services.database_service import DatabaseService
from tests.test_utils.fixtures import postgres_container_fixture  # noqa: F401


@pytest.mark.slow
async def test_database_service(postgres_container_fixture):  # noqa: F811
    url = postgres_container_fixture.get_connection_url()
    database_service = DatabaseService(url)
    assert database_service.engine is not None

    try:
        await database_service.start()
        await database_service.close()
    except Exception as e:
        pytest.fail(f"Connection verification failed: {e}")
