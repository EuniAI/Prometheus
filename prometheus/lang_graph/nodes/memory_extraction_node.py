import logging
import threading

from langchain_core.language_models.chat_models import BaseChatModel

from prometheus.lang_graph.nodes.context_extraction_node import ContextExtractionNode
from prometheus.lang_graph.subgraphs.context_retrieval_state import ContextRetrievalState


class MemoryExtractionNode:
    """Node for extracting useful contexts from memory-retrieved contexts."""

    def __init__(self, model: BaseChatModel, local_path: str):
        """
        Initialize the memory extraction node.

        Args:
            model: LLM model for context extraction
            local_path: Local path to the codebase
        """
        self.context_extraction_node = ContextExtractionNode(model, local_path)
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")

    def __call__(self, state: ContextRetrievalState):
        """
        Extract useful contexts from memory_contexts using the refined query.

        Args:
            state: Current state containing memory_contexts and refined_query

        Returns:
            State update with extracted contexts added to context field
        """
        memory_contexts = state.get("memory_contexts", [])

        if not memory_contexts:
            self._logger.info("No memory contexts to extract")
            return {"context": state.get("context", []), "new_contexts": []}

        self._logger.info(f"Extracting from {len(memory_contexts)} memory contexts")

        # Create a temporary state for extraction with memory contexts as tool messages
        # We need to convert memory contexts to tool messages format
        from langchain_core.messages import ToolMessage

        # Convert memory contexts to a tool message format that context_extraction_node expects
        tool_messages = []
        for ctx in memory_contexts:
            tool_messages.append(
                ToolMessage(
                    content=ctx.content,
                    tool_call_id="memory_retrieval",
                    name="memory_context",
                )
            )

        temp_state = {
            "query": state["query"],
            "refined_query": state.get("refined_query"),
            "context": state.get("context", []),
            "context_provider_messages": tool_messages,
        }

        # Use the existing context extraction node
        result = self.context_extraction_node(temp_state)

        # Get the extracted contexts
        all_contexts = result.get("context", [])
        new_contexts = result.get("new_contexts", [])

        self._logger.info(
            f"Extracted {len(new_contexts)} new contexts from memory "
            f"(total contexts: {len(all_contexts)})"
        )

        return {"context": all_contexts, "new_contexts": new_contexts}
