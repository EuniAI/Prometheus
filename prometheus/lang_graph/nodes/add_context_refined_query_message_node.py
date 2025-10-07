import logging
import threading

from langchain_core.messages import HumanMessage

from prometheus.lang_graph.subgraphs.context_retrieval_state import ContextRetrievalState


class AddContextRefinedQueryMessageNode:
    """Node for converting refined query to string and adding it to context_provider_messages."""

    def __init__(self):
        """Initialize the add context refined query message node."""
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")

    def __call__(self, state: ContextRetrievalState):
        """
        Convert refined query to string and add to context_provider_messages.

        Args:
            state: Current state containing refined_query

        Returns:
            State update with context_provider_messages
        """
        refined_query = state["refined_query"]

        # Build the query message
        query_parts = [f"Essential query: {refined_query.essential_query}"]

        if refined_query.extra_requirements:
            query_parts.append(f"\nExtra requirements: {refined_query.extra_requirements}")

        if refined_query.purpose:
            query_parts.append(f"\nPurpose: {refined_query.purpose}")

        query_message = "".join(query_parts)

        self._logger.info("Creating context provider message from refined query")
        self._logger.debug(f"Query message: {query_message}")

        # Create HumanMessage and add to context_provider_messages
        human_message = HumanMessage(content=query_message)

        return {"context_provider_messages": [human_message]}
