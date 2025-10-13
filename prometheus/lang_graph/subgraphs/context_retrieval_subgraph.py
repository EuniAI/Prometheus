import functools
from typing import Dict, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.lang_graph.nodes.add_context_refined_query_message_node import (
    AddContextRefinedQueryMessageNode,
)
from prometheus.lang_graph.nodes.add_result_context_node import AddResultContextNode
from prometheus.lang_graph.nodes.context_extraction_node import ContextExtractionNode
from prometheus.lang_graph.nodes.context_provider_node import ContextProviderNode
from prometheus.lang_graph.nodes.context_refine_node import ContextRefineNode
from prometheus.lang_graph.nodes.memory_retrieval_node import MemoryRetrievalNode
from prometheus.lang_graph.nodes.memory_storage_node import MemoryStorageNode
from prometheus.lang_graph.nodes.reset_messages_node import ResetMessagesNode
from prometheus.lang_graph.nodes.transform_tool_messages_to_context_node import (
    TransformToolMessagesToContextNode,
)
from prometheus.lang_graph.subgraphs.context_retrieval_state import ContextRetrievalState
from prometheus.models.context import Context


class ContextRetrievalSubgraph:
    """
    This class defines a LangGraph-based subgraph that retrieves relevant code contexts
    using a memory-first strategy. It combines semantic memory (Athena) with knowledge
    graph (Neo4j) retrieval to optimize for cost and speed.

    Workflow:
        1. Refine query into structured format (essential_query, extra_requirements, purpose)
        2. Try to retrieve from semantic memory (Athena)
        3. If found → Merge to result_context (deduplicated & sorted) and refine again (loop)
           If not found → Fall back to Knowledge Graph retrieval
        4. KG retrieval: Query Neo4j → Extract contexts → Store to memory
        5. Loop back to refinement until max iterations

    Flow Diagram:
                                    ┌──────────────┐
                                    │   Refine     │◄─────────────┐
                                    │    Query     │              │
                                    └──────┬───────┘              │
                                           │                      │
                                    ┌──────▼───────┐              │
                                    │   Memory     │              │
                                    │  Retrieval   │              │
                                    │(returns      │              │
                                    │new_contexts) │              │
                                    └──────┬───────┘              │
                                           │                      │
                              ┌────────────┴────────┐             │
                              │                     │             │
                         [has contexts?]            │             │
                              │                     │             │
                    ┌─────────▼─────┐       ┌───────▼─────────┐   │
                    │  Merge to     │       │   KG Provider   │   │
                    │  result       │       │   (with tools)  │   │
                    └─────────┬─────┘       └─────────┬───────┘   │
                              │                       │           │
                              │                  ┌────▼──────┐    │
                              │                  │  Extract  │    │
                              │                  │ Contexts  │    │
                              │                  └────┬──────┘    │
                              │                       │           │
                              │                  ┌────▼──────┐    │
                              │                  │  Store to │    │
                              │                  │  Memory   │    │
                              │                  └────┬──────┘    │
                              │                       │           │
                              └───────────────────────┴───────────┘
    """

    def __init__(
        self,
        base_model: BaseChatModel,
        advanced_model: BaseChatModel,
        kg: KnowledgeGraph,
        local_path: str,
        repository_id: int,
    ):
        """
        Initializes the context retrieval subgraph.

        Args:
            base_model (BaseChatModel): The LLM used for context selection and refinement.
            advanced_model (BaseChatModel): The LLM used for advanced tasks like query refinement and context extraction.
            kg (KnowledgeGraph): Knowledge graph instance
            local_path (str): Local path to the codebase for context extraction.
            repository_id (int): Repository ID for memory storage
        """
        # Step 1: Refine query into structured format
        context_refine_node = ContextRefineNode(model=advanced_model, kg=kg)

        # Step 2: Retrieve contexts from semantic memory (Athena)
        memory_retrieval_node = MemoryRetrievalNode(repository_id=repository_id)

        # Step 3: Extract relevant contexts from explored_context
        context_extraction_node = ContextExtractionNode(model=advanced_model, root_path=local_path)

        # Step 4: Store new contexts to memory
        memory_storage_node = MemoryStorageNode(repository_id=repository_id)

        # Step 5: Merge and deduplicate contexts
        add_result_context_node = AddResultContextNode()

        # Step 6: Convert refined query to message for KG retrieval
        add_context_refined_query_message_node = AddContextRefinedQueryMessageNode()

        # Step 7: Query knowledge graph (Neo4j) using LLM tools
        context_provider_node = ContextProviderNode(model=base_model, kg=kg, local_path=local_path)
        context_provider_tools = ToolNode(
            tools=context_provider_node.tools,
            name="context_provider_tools",
            messages_key="context_provider_messages",
        )
        transform_tool_messages_to_context_node = TransformToolMessagesToContextNode()

        # Step 8: Reset messages for next iteration
        reset_context_provider_messages_node = ResetMessagesNode("context_provider_messages")

        # Define the state machine
        workflow = StateGraph(ContextRetrievalState)

        # Add all nodes to the graph
        workflow.add_node("context_refine_node", context_refine_node)
        workflow.add_node("memory_retrieval_node", memory_retrieval_node)
        workflow.add_node("context_extraction_node", context_extraction_node)
        workflow.add_node("memory_storage_node", memory_storage_node)
        workflow.add_node("add_result_context_node", add_result_context_node)
        workflow.add_node(
            "add_context_refined_query_message_node", add_context_refined_query_message_node
        )
        workflow.add_node("context_provider_node", context_provider_node)
        workflow.add_node("context_provider_tools", context_provider_tools)
        workflow.add_node(
            "transform_tool_messages_to_context_node", transform_tool_messages_to_context_node
        )
        workflow.add_node(
            "reset_context_provider_messages_node", reset_context_provider_messages_node
        )

        # Define workflow edges
        # Entry: Always start with query refinement
        workflow.set_entry_point("context_refine_node")

        # After refine: Check if we have a valid query, if yes try memory first
        workflow.add_conditional_edges(
            "context_refine_node",
            lambda state: bool(state["refined_query"])
            and bool(state["refined_query"].essential_query.strip()),
            {True: "memory_retrieval_node", False: END},
        )

        # After memory retrieval: Check if we found new contexts
        # Yes → Merge to result_context and loop back (memory hit)
        # No → Fall back to KG retrieval (memory miss)
        workflow.add_conditional_edges(
            "memory_retrieval_node",
            lambda state: len(state["new_contexts"]) > 0,
            {True: "add_result_context_node", False: "reset_context_provider_messages_node"},
        )

        # Memory hit path: Merge → Refine again (no storage for memory contexts)
        workflow.add_edge("add_result_context_node", "context_refine_node")

        # Memory miss path: Reset → Convert query → KG provider
        workflow.add_edge(
            "reset_context_provider_messages_node", "add_context_refined_query_message_node"
        )
        workflow.add_edge("add_context_refined_query_message_node", "context_provider_node")

        # KG provider: Call tools if needed, otherwise extract directly
        workflow.add_conditional_edges(
            "context_provider_node",
            functools.partial(tools_condition, messages_key="context_provider_messages"),
            {"tools": "context_provider_tools", END: "transform_tool_messages_to_context_node"},
        )
        # After KG provider (no tools): Transform tool messages → Extract contexts → Store → Merge
        workflow.add_edge("transform_tool_messages_to_context_node", "context_extraction_node")
        workflow.add_edge("context_extraction_node", "memory_storage_node")
        workflow.add_edge("memory_storage_node", "add_result_context_node")

        # After executing tools: Loop back to provider (may call more tools)
        workflow.add_edge("context_provider_tools", "context_provider_node")

        # Compile and store the subgraph
        self.subgraph = workflow.compile()

    def invoke(self, query: str, max_refined_query_loop: int) -> Dict[str, Sequence[Context]]:
        """
        Executes the context retrieval subgraph given an initial query.

        Args:
            query (str): The natural language query representing the information need.
            max_refined_query_loop (int): Maximum number of times the system can refine and retry the query.

        Returns:
            Dict with a single key:
                - "context" (Sequence[Context]): A list of selected context snippets relevant to the query.
        """
        # Set the recursion limit based on the maximum number of refined query loops
        max_refined_query_loop = max_refined_query_loop + 1
        config = {"recursion_limit": max_refined_query_loop * 40}

        input_state = {
            "query": query,
            "max_refined_query_loop": max_refined_query_loop,
        }

        output_state = self.subgraph.invoke(input_state, config)

        return {"context": output_state["context"]}
