from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prometheus.app.entity.invitation_code import InvitationCode
from prometheus.app.services.database_service import DatabaseService
from prometheus.app.services.invitation_code_service import InvitationCodeService
from tests.test_utils.fixtures import postgres_container_fixture  # noqa: F401


@pytest.fixture
async def mock_database_service(postgres_container_fixture):  # noqa: F811
    """Fixture: provide a clean DatabaseService using the Postgres test container."""
    service = DatabaseService(postgres_container_fixture.get_connection_url())
    await service.start()
    yield service
    await service.close()


@pytest.fixture
def service(mock_database_service):
    """Fixture: construct an InvitationCodeService with the database service."""
    return InvitationCodeService(database_service=mock_database_service)


async def _insert_code(
    session: AsyncSession, code: str, is_used: bool = False, expires_in_seconds: int = 3600
) -> InvitationCode:
    """Helper: insert a single InvitationCode with given state and expiration."""
    obj = InvitationCode(
        code=code,
        is_used=is_used,
        expiration_time=datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds),
    )
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def test_create_invitation_code(service):
    """Test that create_invitation_code correctly generates and returns an InvitationCode."""
    invitation_code = await service.create_invitation_code()

    # Verify the returned object is an InvitationCode instance
    assert isinstance(invitation_code, InvitationCode)
    assert isinstance(invitation_code.code, str)
    assert len(invitation_code.code) == 36  # uuid4 string length
    assert invitation_code.id is not None

    # Verify the object is persisted in the database
    async with AsyncSession(service.engine) as session:
        db_obj = await session.get(InvitationCode, invitation_code.id)
        assert db_obj is not None
        assert db_obj.code == invitation_code.code


async def test_list_invitation_codes(service):
    """Test that list_invitation_codes returns all stored invitation codes."""
    # Insert two invitation codes first
    code1 = await service.create_invitation_code()
    code2 = await service.create_invitation_code()

    codes = await service.list_invitation_codes()

    # Verify length
    assert len(codes) >= 2
    # Verify both created codes are included
    all_codes = [c.code for c in codes]
    assert code1.code in all_codes
    assert code2.code in all_codes


async def test_check_invitation_code_returns_false_when_not_exists(service):
    """check_invitation_code should return False if the code does not exist."""
    ok = await service.check_invitation_code("non-existent-code")
    assert ok is False


async def test_check_invitation_code_returns_false_when_used(service):
    """check_invitation_code should return False if the code is already used."""
    async with AsyncSession(service.engine) as session:
        await _insert_code(session, "used-code", is_used=True, expires_in_seconds=3600)

    ok = await service.check_invitation_code("used-code")
    assert ok is False


async def test_check_invitation_code_returns_false_when_expired(service):
    """check_invitation_code should return False if the code is expired."""
    async with AsyncSession(service.engine) as session:
        # Negative expires_in_seconds makes it expire in the past
        await _insert_code(session, "expired-code", is_used=False, expires_in_seconds=-60)

    ok = await service.check_invitation_code("expired-code")
    assert ok is False


async def test_check_invitation_code_returns_true_when_valid(service):
    """check_invitation_code should return True if the code exists, not used, and not expired."""
    async with AsyncSession(service.engine) as session:
        await _insert_code(session, "valid-code", is_used=False, expires_in_seconds=3600)

    ok = await service.check_invitation_code("valid-code")
    assert ok is True


async def test_mark_code_as_used_persists_state(service):
    """mark_code_as_used should set 'used' to True and persist to DB."""
    async with AsyncSession(service.engine) as session:
        created = await _insert_code(session, "to-use", is_used=False, expires_in_seconds=3600)
        created_id = created.id

    # Act
    await service.mark_code_as_used("to-use")

    # Assert persisted state
    async with AsyncSession(service.engine) as session:
        refreshed = await session.get(InvitationCode, created_id)
        assert refreshed is not None
        assert refreshed.is_used is True
