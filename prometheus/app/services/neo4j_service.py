"""Service for managing Neo4j database driver."""

import logging

from neo4j import AsyncGraphDatabase

from prometheus.app.services.base_service import BaseService
from prometheus.utils.logger_manager import get_thread_logger


class Neo4jService(BaseService):
    def __init__(self, neo4j_uri: str, neo4j_username: str, neo4j_password: str):
        self._logger, file_handler = get_thread_logger(__name__)
        self.neo4j_driver = AsyncGraphDatabase.driver(
            neo4j_uri,
            auth=(neo4j_username, neo4j_password),
            connection_timeout=1200,
            max_transaction_retry_time=1200,
            keep_alive=True,
        )

    async def close(self):
        await self.neo4j_driver.close()
        self._logger.info("Neo4j driver connection closed.")
