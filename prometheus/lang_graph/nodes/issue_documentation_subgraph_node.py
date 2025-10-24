import logging
import threading

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.errors import GraphRecursionError

from prometheus.git.git_repository import GitRepository
from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.lang_graph.graphs.issue_state import IssueState
from prometheus.lang_graph.subgraphs.issue_documentation_subgraph import (
    IssueDocumentationSubgraph,
)


class IssueDocumentationSubgraphNode:
    """
    A LangGraph node that handles the issue documentation subgraph,
    which is responsible for updating documentation based on a GitHub issue.
    """

    def __init__(
        self,
        advanced_model: BaseChatModel,
        base_model: BaseChatModel,
        kg: KnowledgeGraph,
        git_repo: GitRepository,
        repository_id: int,
    ):
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")
        self.issue_documentation_subgraph = IssueDocumentationSubgraph(
            advanced_model=advanced_model,
            base_model=base_model,
            kg=kg,
            git_repo=git_repo,
            repository_id=repository_id,
        )

    def __call__(self, state: IssueState):
        # Logging entry into the node
        self._logger.info("Enter IssueDocumentationSubgraphNode")

        try:
            output_state = self.issue_documentation_subgraph.invoke(
                issue_title=state["issue_title"],
                issue_body=state["issue_body"],
                issue_comments=state["issue_comments"],
            )
        except GraphRecursionError:
            # Handle recursion error gracefully
            self._logger.critical(
                "Please increase the recursion limit of IssueDocumentationSubgraph"
            )
            return {
                "edit_patch": None,
                "passed_reproducing_test": False,
                "passed_regression_test": False,
                "passed_existing_test": False,
                "issue_response": None,
            }

        # Logging the issue response for debugging
        self._logger.info(f"issue_response:\n{output_state['issue_response']}")
        return {
            "edit_patch": output_state["edit_patch"],
            "passed_reproducing_test": output_state["passed_reproducing_test"],
            "passed_regression_test": output_state["passed_regression_test"],
            "passed_existing_test": output_state["passed_existing_test"],
            "issue_response": output_state["issue_response"],
        }
