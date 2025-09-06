from typing import Dict

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.errors import GraphRecursionError

from prometheus.docker.base_container import BaseContainer
from prometheus.git.git_repository import GitRepository
from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.lang_graph.subgraphs.bug_get_regression_tests_subgraph import (
    BugGetRegressionTestsSubgraph,
)
from prometheus.utils.logger_manager import get_thread_logger


class BugGetRegressionTestsSubgraphNode:
    def __init__(
        self,
        advanced_model: BaseChatModel,
        base_model: BaseChatModel,
        container: BaseContainer,
        kg: KnowledgeGraph,
        git_repo: GitRepository,
    ):
        self._logger, file_handler = get_thread_logger(__name__)
        self.subgraph = BugGetRegressionTestsSubgraph(
            advanced_model=advanced_model,
            base_model=base_model,
            container=container,
            kg=kg,
            git_repo=git_repo,
        )

    def __call__(self, state: Dict):
        self._logger.info("Enter bug_get_regression_tests_subgraph_node")
        try:
            output_state = self.subgraph.invoke(
                issue_title=state["issue_title"],
                issue_body=state["issue_body"],
                issue_comments=state["issue_comments"],
            )
        except GraphRecursionError:
            self._logger.info("Recursion limit reached, returning empty regression tests")
            return {"selected_regression_tests": []}
        self._logger.debug(
            f"Selected {len(output_state['regression_tests'])} regression tests: {output_state['regression_tests']}"
        )
        return {"selected_regression_tests": output_state["regression_tests"]}
