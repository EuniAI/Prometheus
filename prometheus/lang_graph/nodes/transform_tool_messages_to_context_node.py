import logging
import threading

from prometheus.lang_graph.subgraphs.context_retrieval_state import ContextRetrievalState
from prometheus.utils.knowledge_graph_utils import deduplicate_contexts, sort_contexts
from prometheus.utils.lang_graph_util import (
    extract_last_tool_messages,
    transform_tool_messages_to_context,
)


class TransformToolMessagesToContextNode:
    """Node for transforming tool messages into Context objects and adding them to explored_context.

    This node extracts artifacts from tool messages (after the last human message),
    converts them to Context objects using the knowledge graph data generator,
    and adds them to the explored_context field in the state.
    """

    def __init__(self):
        """Initialize the transform tool messages to context node."""
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")

    def __call__(self, state: ContextRetrievalState):
        """
        Transform tool messages to Context objects and add to explored_context.

        Args:
            state: Current state containing context_provider_messages

        Returns:
            State update with Context objects added to explored_context
        """
        # Extract tool messages from the message history
        context_provider_messages = state.get("context_provider_messages", [])
        tool_messages = extract_last_tool_messages(context_provider_messages)

        # Transform tool messages to Context objects
        explored_context = transform_tool_messages_to_context(tool_messages)

        if not explored_context:
            self._logger.info("No contexts extracted from tool messages")
            return {"explored_context": []}

        return {"explored_context": sort_contexts(deduplicate_contexts(explored_context))}
