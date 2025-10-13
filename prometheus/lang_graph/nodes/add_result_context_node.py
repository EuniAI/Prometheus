import logging
import threading

from prometheus.lang_graph.subgraphs.context_retrieval_state import ContextRetrievalState
from prometheus.utils.knowledge_graph_utils import deduplicate_contexts, sort_contexts


class AddResultContextNode:
    """Node for adding new_contexts to context and deduplicating the result."""

    def __init__(self):
        """Initialize the add result context node."""
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")

    def __call__(self, state: ContextRetrievalState):
        """
        Add new_contexts to context and deduplicate.

        Args:
            state: Current state containing context and new_contexts

        Returns:
            State update with deduplicated context
        """
        existing_context = state.get("context", [])
        new_contexts = state.get("new_contexts", [])

        if not new_contexts:
            self._logger.info("No new contexts to add")
            return {"context": existing_context}

        self._logger.info(
            f"Adding {len(new_contexts)} new contexts to {len(existing_context)} existing contexts"
        )

        # Combine existing and new contexts
        combined_contexts = list(existing_context) + list(new_contexts)

        # Deduplicate
        deduplicated_contexts = deduplicate_contexts(combined_contexts)

        self._logger.info(
            f"After deduplication: {len(deduplicated_contexts)} total contexts "
            f"(removed {len(combined_contexts) - len(deduplicated_contexts)} duplicates)"
        )

        # Sort contexts before returning and record previous queries
        return {
            "context": sort_contexts(deduplicated_contexts),
            "previous_refined_queries": [state["refined_query"]],
        }
