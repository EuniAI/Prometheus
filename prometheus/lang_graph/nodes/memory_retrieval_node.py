import logging
import threading

from prometheus.lang_graph.subgraphs.context_retrieval_state import ContextRetrievalState
from prometheus.models.context import Context
from prometheus.utils.knowledge_graph_utils import deduplicate_contexts, sort_contexts
from prometheus.utils.memory_utils import retrieve_memory


class MemoryRetrievalNode:
    """Node for retrieving contexts from Athena semantic memory."""

    def __init__(self, repository_id: int):
        """
        Initialize the memory retrieval node.

        Args:
            repository_id: Repository identifier for memory storage
        """
        self.repository_id = repository_id
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")

    def __call__(self, state: ContextRetrievalState):
        """
        Retrieve contexts from memory using the refined query.
        Memory contexts are directly added to new_contexts (deduplicated and sorted).

        Args:
            state: Current state containing the refined query

        Returns:
            State update with new_contexts containing deduplicated and sorted memory contexts
        """
        refined_query = state["refined_query"]

        try:
            self._logger.info(
                f"Retrieving contexts from memory for query: {refined_query.essential_query}"
            )
            results = retrieve_memory(repository_id=self.repository_id, query=refined_query)
        except Exception as e:
            self._logger.error(f"Failed to retrieve from memory: {e}")
            # On error, return empty list to continue with normal flow
            return {"new_contexts": []}

        self._logger.debug(f"Retrieved contexts: {results}")
        # Extract contexts from the result
        memory_contexts = []
        for memory in results:
            for context in memory["memory_context_contexts"]:
                memory_contexts.append(Context(**context))
        self._logger.info(f"Retrieved {len(results)} memories from memory")
        self._logger.info(f"Retrieved {len(memory_contexts)} contexts from memory")

        # Deduplicate and sort contexts before returning as new_contexts
        deduplicated_sorted = sort_contexts(deduplicate_contexts(memory_contexts))
        self._logger.info(
            f"After deduplication and sorting: {len(deduplicated_sorted)} contexts from memory"
        )
        return {"new_contexts": deduplicated_sorted}
