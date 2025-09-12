import logging
import threading

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.errors import GraphRecursionError

from prometheus.docker.base_container import BaseContainer
from prometheus.git.git_repository import GitRepository
from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.lang_graph.subgraphs.issue_bug_state import IssueBugState
from prometheus.lang_graph.subgraphs.issue_verified_bug_subgraph import IssueVerifiedBugSubgraph


class IssueVerifiedBugSubgraphNode:
    """
    A LangGraph node that handles the verified issue bug, which is responsible for solving bugs.
    """

    def __init__(
        self,
        advanced_model: BaseChatModel,
        base_model: BaseChatModel,
        container: BaseContainer,
        kg: KnowledgeGraph,
        git_repo: GitRepository,
    ):
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")
        self.git_repo = git_repo
        self.issue_reproduced_bug_subgraph = IssueVerifiedBugSubgraph(
            advanced_model=advanced_model,
            base_model=base_model,
            container=container,
            kg=kg,
            git_repo=git_repo,
        )

    def __call__(self, state: IssueBugState):
        self._logger.info("Enter IssueVerifiedBugSubgraphNode")
        try:
            output_state = self.issue_reproduced_bug_subgraph.invoke(
                issue_title=state["issue_title"],
                issue_body=state["issue_body"],
                issue_comments=state["issue_comments"],
                number_of_candidate_patch=state["number_of_candidate_patch"],
                run_regression_test=state["run_regression_test"],
                run_existing_test=state["run_existing_test"],
                reproduced_bug_file=state["reproduced_bug_file"],
                reproduced_bug_commands=state["reproduced_bug_commands"],
                reproduced_bug_patch=state["reproduced_bug_patch"],
                selected_regression_tests=state["selected_regression_tests"]
                if state["run_regression_test"]
                else None,
            )
        except GraphRecursionError:
            self._logger.info("Recursion limit reached")
            return {
                "edit_patch": None,
                "passed_reproducing_test": False,
                "passed_existing_test": False,
                "passed_regression_test": False,
            }
        finally:
            self.git_repo.reset_repository()

        # Log the generated patch
        self._logger.info(f"edit_patch: {output_state['edit_patch']}")
        return {
            "edit_patch": output_state["edit_patch"],
            "passed_reproducing_test": True if state["run_reproduce_test"] else False,
            "passed_existing_test": True if state["run_existing_test"] else False,
            "passed_regression_test": True
            if state["run_regression_test"] and state["selected_regression_tests"]
            else False,
        }
