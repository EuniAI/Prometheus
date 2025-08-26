import datetime
import logging
import uuid
from typing import Sequence

from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from prometheus.app.entity.invitation_code import InvitationCode
from prometheus.app.services.base_service import BaseService
from prometheus.app.services.database_service import DatabaseService


class InvitationCodeService(BaseService):
    def __init__(self, database_service: DatabaseService):
        self.database_service = database_service
        self.engine = database_service.engine
        self._logger = logging.getLogger("prometheus.app.services.invitation_code_service")

    async def create_invitation_code(self) -> InvitationCode:
        """
        Create a new invitation code and commit it to the database.

        Returns:
            InvitationCode: The created invitation code instance.
        """
        async with AsyncSession(self.engine) as session:
            code = str(uuid.uuid4())
            invitation_code = InvitationCode(code=code)
            session.add(invitation_code)
            await session.commit()
            await session.refresh(invitation_code)
            return invitation_code

    async def list_invitation_codes(self) -> Sequence[InvitationCode]:
        """
        List all invitation codes from the database.

        Returns:
            Sequence[InvitationCode]: A list of all invitation code instances.
        """
        async with AsyncSession(self.engine) as session:
            statement = select(InvitationCode)
            result = await session.execute(statement)
            return result.scalars().all()

    async def check_invitation_code(self, code: str) -> bool:
        """
        Check if an invitation code is valid (exists, not used and not expired).
        """
        async with AsyncSession(self.engine) as session:
            statement = select(InvitationCode).where(InvitationCode.code == code)
            result = await session.execute(statement)
            invitation_code = result.scalar_one_or_none()
            if not invitation_code:
                return False
            if invitation_code.is_used:
                return False

            exp = invitation_code.expiration_time
            # If our database returned a naive datetime, assume it's UTC
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=datetime.timezone.utc)
            if exp < datetime.datetime.now(datetime.timezone.utc):
                return False
            return True

    async def mark_code_as_used(self, code: str) -> None:
        """
        Mark an invitation code as used.
        """
        async with AsyncSession(self.engine) as session:
            statement = select(InvitationCode).where(InvitationCode.code == code)
            result = await session.execute(statement)
            invitation_code = result.scalar_one_or_none()
            if invitation_code:
                invitation_code.is_used = True
                session.add(invitation_code)
                await session.commit()
