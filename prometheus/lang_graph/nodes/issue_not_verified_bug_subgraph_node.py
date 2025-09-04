import threading
from typing import Dict

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.errors import GraphRecursionError

from prometheus.docker.base_container import BaseContainer
from prometheus.git.git_repository import GitRepository
from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.lang_graph.subgraphs.issue_not_verified_bug_subgraph import (
    IssueNotVerifiedBugSubgraph,
)
from prometheus.utils.logger_manager import get_logger


class IssueNotVerifiedBugSubgraphNode:
    def __init__(
        self,
        advanced_model: BaseChatModel,
        base_model: BaseChatModel,
        kg: KnowledgeGraph,
        git_repo: GitRepository,
        container: BaseContainer,
    ):
        self._logger = get_logger(f"thread-{threading.get_ident()}.{__name__}")

        self.issue_not_verified_bug_subgraph = IssueNotVerifiedBugSubgraph(
            advanced_model=advanced_model,
            base_model=base_model,
            kg=kg,
            git_repo=git_repo,
            container=container,
        )
        self.git_repo = git_repo

    def __call__(self, state: Dict):
        self._logger.info("Enter IssueNotVerifiedBugSubgraphNode")

        try:
            output_state = self.issue_not_verified_bug_subgraph.invoke(
                issue_title=state["issue_title"],
                issue_body=state["issue_body"],
                issue_comments=state["issue_comments"],
                number_of_candidate_patch=state["number_of_candidate_patch"],
                run_regression_test=state["run_regression_test"],
                selected_regression_tests=state["selected_regression_tests"]
                if state["run_regression_test"]
                else None,
            )
        except GraphRecursionError:
            self._logger.debug("GraphRecursionError encountered, returning empty patch")
            return {
                "edit_patch": None,
                "passed_reproducing_test": False,
                "passed_regression_test": False,
                "passed_existing_test": False,
            }
        finally:
            self.git_repo.reset_repository()

        self._logger.info(f"final_patch:\n{output_state['final_patch']}")

        return {
            "edit_patch": output_state["final_patch"],
            "passed_reproducing_test": False,
            "passed_regression_test": True
            if state["run_regression_test"] and state["selected_regression_tests"]
            else False,
            "passed_existing_test": False,
        }
