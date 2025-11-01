import logging
import threading

from prometheus.exceptions.memory_exception import MemoryException
from prometheus.lang_graph.subgraphs.context_retrieval_state import ContextRetrievalState
from prometheus.utils.memory_utils import store_memory


class MemoryStorageNode:
    """Node for storing contexts to Athena semantic memory."""

    def __init__(self, repository_id: int):
        """
        Initialize the memory storage node.

        Args:
            repository_id: Repository identifier for memory storage
        """
        self.repository_id = repository_id
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")

    def __call__(self, state: ContextRetrievalState):
        """
        Store newly extracted contexts to memory.

        Args:
            state: Current state containing refined query and new contexts

        Returns:
            Empty state update (storage is side-effect only)
        """
        refined_query = state["refined_query"]
        new_contexts = state["new_contexts"]

        self._logger.info(
            f"Storing {len(new_contexts)} contexts to memory for query: {refined_query.essential_query}"
        )

        try:
            store_memory(
                repository_id=self.repository_id,
                essential_query=refined_query.essential_query,
                extra_requirements=refined_query.extra_requirements or "",
                purpose=refined_query.purpose or "",
                contexts=list(new_contexts),
            )
        except MemoryException as e:
            self._logger.error(f"Failed to store to memory: {e}")
            # Don't fail the entire flow if memory storage fails

        self._logger.info("Successfully stored contexts to memory")
        return None
