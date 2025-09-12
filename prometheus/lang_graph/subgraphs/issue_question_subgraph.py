import functools
from typing import Mapping, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from prometheus.git.git_repository import GitRepository
from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.lang_graph.nodes.context_retrieval_subgraph_node import ContextRetrievalSubgraphNode
from prometheus.lang_graph.nodes.issue_question_analyzer_message_node import (
    IssueQuestionAnalyzerMessageNode,
)
from prometheus.lang_graph.nodes.issue_question_analyzer_node import IssueQuestionAnalyzerNode
from prometheus.lang_graph.nodes.issue_question_context_message_node import (
    IssueQuestionContextMessageNode,
)
from prometheus.lang_graph.nodes.issue_question_response_node import IssueQuestionResponderNode
from prometheus.lang_graph.subgraphs.issue_question_state import IssueQuestionState


class IssueQuestionSubgraph:
    """
    A LangGraph-based subgraph to analyze and answer questions related to GitHub issues.
    This subgraph processes issue details, retrieves relevant context, and generates a comprehensive response.
    """

    def __init__(
        self,
        advanced_model: BaseChatModel,
        base_model: BaseChatModel,
        kg: KnowledgeGraph,
        git_repo: GitRepository,
    ):
        # Step 1: Retrieve relevant context based on the issue details
        issue_question_context_message_node = IssueQuestionContextMessageNode()
        context_retrieval_subgraph_node = ContextRetrievalSubgraphNode(
            model=base_model,
            kg=kg,
            local_path=git_repo.playground_path,
            query_key_name="question_query",
            context_key_name="question_context",
        )

        # Step 2: Send issue question analyze message
        issue_question_analyzer_message_node = IssueQuestionAnalyzerMessageNode()
        issue_question_analyzer_node = IssueQuestionAnalyzerNode(model=advanced_model)
        issue_question_analyzer_tools = ToolNode(
            tools=issue_question_analyzer_node.tools,
            name="issue_question_analyzer_tools",
            messages_key="issue_question_analyzer_messages",
        )

        # Step 3: Get the last response as the final answer
        issue_question_responder_node = IssueQuestionResponderNode()

        # Define the subgraph structure
        workflow = StateGraph(IssueQuestionState)
        workflow.add_node(
            "issue_question_context_message_node", issue_question_context_message_node
        )
        workflow.add_node("context_retrieval_subgraph_node", context_retrieval_subgraph_node)

        workflow.add_node(
            "issue_question_analyzer_message_node", issue_question_analyzer_message_node
        )
        workflow.add_node("issue_question_analyzer_node", issue_question_analyzer_node)
        workflow.add_node("issue_question_analyzer_tools", issue_question_analyzer_tools)

        workflow.add_node("issue_question_responder_node", issue_question_responder_node)

        # Define the entry point
        workflow.set_entry_point("issue_question_context_message_node")

        # Define the workflow transitions
        workflow.add_edge("issue_question_context_message_node", "context_retrieval_subgraph_node")
        workflow.add_edge("context_retrieval_subgraph_node", "issue_question_analyzer_message_node")

        workflow.add_edge("issue_question_analyzer_message_node", "issue_question_analyzer_node")
        workflow.add_conditional_edges(
            "issue_question_analyzer_node",
            functools.partial(tools_condition, messages_key="issue_question_analyzer_messages"),
            {"tools": "issue_question_analyzer_tools", END: "issue_question_responder_node"},
        )
        workflow.add_edge("issue_question_analyzer_tools", "issue_question_analyzer_node")

        workflow.add_edge("issue_question_responder_node", END)

        # Compile the workflow into an executable subgraph
        self.subgraph = workflow.compile()

    def invoke(
        self,
        issue_title: str,
        issue_body: str,
        issue_comments: Sequence[Mapping[str, str]],
        recursion_limit: int = 50,
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
            "edit_patch": None,
            "passed_reproducing_test": False,
            "passed_existing_test": False,
            "passed_regression_test": False,
            "issue_response": output_state["question_response"],
        }
