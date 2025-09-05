from typing import Optional, Sequence

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import or_, select

from prometheus.app.entity.user import User
from prometheus.app.services.base_service import BaseService
from prometheus.app.services.database_service import DatabaseService
from prometheus.exceptions.server_exception import ServerException
from prometheus.utils.jwt_utils import JWTUtils
from prometheus.utils.logger_manager import get_thread_logger


class UserService(BaseService):
    def __init__(self, database_service: DatabaseService):
        self.database_service = database_service
        self.engine = database_service.engine
        self._logger, file_handler = get_thread_logger(__name__)
        self.ph = PasswordHasher()
        self.jwt_utils = JWTUtils()

    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        github_token: Optional[str] = None,
        issue_credit: int = 0,
        is_superuser: bool = False,
    ) -> None:
        """
        Create a new superuser and commit it to the database.

        Args:
            username (str): Desired username.
            email (str): Email address.
            password (str): Plaintext password (will be hashed).
            github_token (Optional[str]): Optional GitHub token.
            issue_credit (int): Optional issue credit.
            is_superuser (bool): Whether the user is a superuser.
        Returns:
            User: The created superuser instance.
        """
        async with AsyncSession(self.engine) as session:
            statement = select(User).where(User.username == username)
            if (await session.execute(statement)).scalar_one_or_none():
                raise ServerException(400, f"Username '{username}' already exists")
            statement = select(User).where(User.email == email)
            if (await session.execute(statement)).scalar_one_or_none():
                raise ServerException(400, f"Email '{email}' already exists")

            hashed_password = self.ph.hash(password)

            user = User(
                username=username,
                email=email,
                password_hash=hashed_password,
                github_token=github_token,
                issue_credit=issue_credit,
                is_superuser=is_superuser,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

    async def login(self, username: str, email: str, password: str) -> str:
        """
        Log in a user by verifying their credentials and return an access token.

        Args:
            username (str): Username of the user.
            email (str): Email address of the user.
            password (str): Plaintext password.
        """
        async with AsyncSession(self.engine) as session:
            statement = select(User).where(or_(User.username == username, User.email == email))
            user = (await session.execute(statement)).scalar_one_or_none()

            if not user:
                raise ServerException(code=400, message="Invalid username or email")

            try:
                self.ph.verify(user.password_hash, password)
            except VerifyMismatchError:
                raise ServerException(code=400, message="Invalid password")

            # Generate and return a JWT token for the user
            token = self.jwt_utils.generate_token({"user_id": user.id})
            return token

    # Create a superuser and commit it to the database
    async def create_superuser(
        self,
        username: str,
        email: str,
        password: str,
        github_token: Optional[str] = None,
    ) -> None:
        """
        Create a new superuser in the database.

        This method creates a superuser with the provided credentials and commits it to the database.
        """
        await self.create_user(
            username, email, password, github_token, is_superuser=True, issue_credit=999999
        )
        self._logger.info(f"Superuser '{username}' created successfully.")

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """
        Retrieve a user by their ID.

        Args:
            user_id (int): The ID of the user to retrieve.

        Returns:
            User: The user instance if found, otherwise None.
        """
        async with AsyncSession(self.engine) as session:
            statement = select(User).where(User.id == user_id)
            return (await session.execute(statement)).scalar_one_or_none()

    async def get_issue_credit(self, user_id: int) -> int:
        """
        Retrieve the issue credit of a user by their ID.

        Args:
            user_id (int): The ID of the user.

        Returns:
            int: The issue credit of the user.
        """
        async with AsyncSession(self.engine) as session:
            statement = select(User.issue_credit).where(User.id == user_id)
            result = (await session.execute(statement)).scalar_one_or_none()
            return int(result) if result else 0

    async def update_issue_credit(self, user_id: int, new_issue_credit) -> None:
        """
        Update the issue credit of a user by their ID.

        Args:
            user_id (int): The ID of the user.
            new_issue_credit (int): The new issue credit.
        """
        async with AsyncSession(self.engine) as session:
            statement = select(User).where(User.id == user_id)
            user = (await session.execute(statement)).scalar_one_or_none()
            if user:
                user.issue_credit = new_issue_credit
                session.add(user)
                await session.commit()

    async def is_admin(self, user_id):
        """
        Check if a user is an admin (superuser) by their ID.
        """
        async with AsyncSession(self.engine) as session:
            statement = select(User).where(User.id == user_id)
            user = (await session.execute(statement)).scalar_one_or_none()
            return user.is_superuser if user else False

    async def list_users(self) -> Sequence[User]:
        """
        List all users in the database.
        """
        async with AsyncSession(self.engine) as session:
            statement = select(User)
            users = (await session.execute(statement)).scalars().all()
            return users

    async def set_github_token(self, user_id: int, github_token: str):
        """
        Set GitHub token for a user by their ID.
        """
        async with AsyncSession(self.engine) as session:
            statement = select(User).where(User.id == user_id)
            user = (await session.execute(statement)).scalar_one_or_none()
            if user:
                user.github_token = github_token
                session.add(user)
                await session.commit()
                await session.refresh(user)
