import functools
from typing import Mapping, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from prometheus.git.git_repository import GitRepository
from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.lang_graph.nodes.context_retrieval_subgraph_node import ContextRetrievalSubgraphNode
from prometheus.lang_graph.nodes.edit_node import EditNode
from prometheus.lang_graph.nodes.git_diff_node import GitDiffNode
from prometheus.lang_graph.nodes.issue_documentation_analyzer_message_node import (
    IssueDocumentationAnalyzerMessageNode,
)
from prometheus.lang_graph.nodes.issue_documentation_analyzer_node import (
    IssueDocumentationAnalyzerNode,
)
from prometheus.lang_graph.nodes.issue_documentation_context_message_node import (
    IssueDocumentationContextMessageNode,
)
from prometheus.lang_graph.nodes.issue_documentation_edit_message_node import (
    IssueDocumentationEditMessageNode,
)
from prometheus.lang_graph.nodes.issue_documentation_responder_node import (
    IssueDocumentationResponderNode,
)
from prometheus.lang_graph.subgraphs.issue_documentation_state import IssueDocumentationState


class IssueDocumentationSubgraph:
    """
    A LangGraph-based subgraph to handle documentation update requests for GitHub issues.

    This subgraph processes documentation requests by:
    1. Retrieving relevant documentation and source code context
    2. Analyzing the request and creating a documentation update plan
    3. Implementing the documentation changes using file operations
    4. Generating a patch with the documentation updates
    5. Creating a response summarizing the documentation changes
    """

    def __init__(
        self,
        advanced_model: BaseChatModel,
        base_model: BaseChatModel,
        kg: KnowledgeGraph,
        git_repo: GitRepository,
        repository_id: int,
    ):
        # Step 1: Retrieve relevant context (documentation files and source code)
        issue_documentation_context_message_node = IssueDocumentationContextMessageNode()
        context_retrieval_subgraph_node = ContextRetrievalSubgraphNode(
            base_model=base_model,
            advanced_model=advanced_model,
            kg=kg,
            local_path=git_repo.playground_path,
            query_key_name="documentation_query",
            context_key_name="documentation_context",
            repository_id=repository_id,
        )

        # Step 2: Analyze the documentation request and create a plan
        issue_documentation_analyzer_message_node = IssueDocumentationAnalyzerMessageNode()
        issue_documentation_analyzer_node = IssueDocumentationAnalyzerNode(model=advanced_model)
        issue_documentation_analyzer_tools = ToolNode(
            tools=issue_documentation_analyzer_node.tools,
            name="issue_documentation_analyzer_tools",
            messages_key="issue_documentation_analyzer_messages",
        )

        # Step 3: Implement the documentation changes
        issue_documentation_edit_message_node = IssueDocumentationEditMessageNode()
        edit_node = EditNode(advanced_model, git_repo.playground_path, kg)
        edit_tools = ToolNode(
            tools=edit_node.tools,
            name="edit_tools",
            messages_key="edit_messages",
        )

        # Step 4: Generate patch from changes
        git_diff_node = GitDiffNode(git_repo, "edit_patch", return_list=False)

        # Step 5: Generate response summarizing the changes
        issue_documentation_responder_node = IssueDocumentationResponderNode(model=base_model)

        # Define the subgraph structure
        workflow = StateGraph(IssueDocumentationState)

        # Add all nodes
        workflow.add_node(
            "issue_documentation_context_message_node",
            issue_documentation_context_message_node,
        )
        workflow.add_node("context_retrieval_subgraph_node", context_retrieval_subgraph_node)

        workflow.add_node(
            "issue_documentation_analyzer_message_node",
            issue_documentation_analyzer_message_node,
        )
        workflow.add_node("issue_documentation_analyzer_node", issue_documentation_analyzer_node)
        workflow.add_node("issue_documentation_analyzer_tools", issue_documentation_analyzer_tools)

        workflow.add_node(
            "issue_documentation_edit_message_node", issue_documentation_edit_message_node
        )
        workflow.add_node("edit_node", edit_node)
        workflow.add_node("edit_tools", edit_tools)

        workflow.add_node("git_diff_node", git_diff_node)
        workflow.add_node("issue_documentation_responder_node", issue_documentation_responder_node)

        # Define the entry point
        workflow.set_entry_point("issue_documentation_context_message_node")

        # Define the workflow transitions
        workflow.add_edge(
            "issue_documentation_context_message_node", "context_retrieval_subgraph_node"
        )
        workflow.add_edge(
            "context_retrieval_subgraph_node", "issue_documentation_analyzer_message_node"
        )

        workflow.add_edge(
            "issue_documentation_analyzer_message_node", "issue_documentation_analyzer_node"
        )
        workflow.add_conditional_edges(
            "issue_documentation_analyzer_node",
            functools.partial(
                tools_condition, messages_key="issue_documentation_analyzer_messages"
            ),
            {
                "tools": "issue_documentation_analyzer_tools",
                END: "issue_documentation_edit_message_node",
            },
        )
        workflow.add_edge("issue_documentation_analyzer_tools", "issue_documentation_analyzer_node")

        workflow.add_edge("issue_documentation_edit_message_node", "edit_node")
        workflow.add_conditional_edges(
            "edit_node",
            functools.partial(tools_condition, messages_key="edit_messages"),
            {"tools": "edit_tools", END: "git_diff_node"},
        )
        workflow.add_edge("edit_tools", "edit_node")

        workflow.add_edge("git_diff_node", "issue_documentation_responder_node")
        workflow.add_edge("issue_documentation_responder_node", END)

        # Compile the workflow into an executable subgraph
        self.subgraph = workflow.compile()

    def invoke(
        self,
        issue_title: str,
        issue_body: str,
        issue_comments: Sequence[Mapping[str, str]],
        recursion_limit: int = 150,
    ):
        config = {"recursion_limit": recursion_limit}

        input_state = {
            "issue_title": issue_title,
            "issue_body": issue_body,
            "issue_comments": issue_comments,
            "max_refined_query_loop": 3,
        }

        output_state = self.subgraph.invoke(input_state, config)
        return {
            "edit_patch": output_state["edit_patch"],
            "passed_reproducing_test": False,
            "passed_existing_test": False,
            "passed_regression_test": False,
            "issue_response": output_state["issue_response"],
        }
