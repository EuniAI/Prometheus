import logging

from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

from prometheus.app.services.base_service import BaseService
from prometheus.utils.logger_manager import get_logger


class DatabaseService(BaseService):
    def __init__(self, DATABASE_URL: str):
        self.engine = create_async_engine(DATABASE_URL, echo=True)
        self._logger = get_logger(__name__)

    # Create the database and tables
    async def create_db_and_tables(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    async def start(self):
        """
        Start the database service by creating the database and tables.
        This method is called when the service is initialized.
        """
        await self.create_db_and_tables()
        self._logger.info("Database and tables created successfully.")

    async def close(self):
        """
        Close the database connection and release any resources.
        """
        await self.engine.dispose()
        self._logger.info("Database connection closed.")
