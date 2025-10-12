import logging
import threading

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.errors import GraphRecursionError

from prometheus.docker.base_container import BaseContainer
from prometheus.git.git_repository import GitRepository
from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.lang_graph.graphs.issue_state import IssueState
from prometheus.lang_graph.subgraphs.issue_feature_subgraph import IssueFeatureSubgraph


class IssueFeatureSubgraphNode:
    """
    A LangGraph node that handles the issue feature subgraph, which is responsible for implementing
    feature requests in a GitHub issue.
    """

    def __init__(
        self,
        advanced_model: BaseChatModel,
        base_model: BaseChatModel,
        container: BaseContainer,
        kg: KnowledgeGraph,
        git_repo: GitRepository,
        repository_id: int,
    ):
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")
        self.container = container
        self.issue_feature_subgraph = IssueFeatureSubgraph(
            advanced_model=advanced_model,
            base_model=base_model,
            kg=kg,
            git_repo=git_repo,
            container=container,
            repository_id=repository_id,
        )

    def __call__(self, state: IssueState):
        # Ensure the container is built and started
        self.container.build_docker_image()
        self.container.start_container()

        # Run the build if needed
        if state["run_build"]:
            self.container.run_build()

        self._logger.info("Enter IssueFeatureSubgraphNode")

        try:
            output_state = self.issue_feature_subgraph.invoke(
                issue_title=state["issue_title"],
                issue_body=state["issue_body"],
                issue_comments=state["issue_comments"],
                number_of_candidate_patch=state["number_of_candidate_patch"],
                run_regression_test=state["run_regression_test"],
                selected_regression_tests=[],  # Can be enhanced to select tests based on modified files
            )
        except GraphRecursionError:
            self._logger.critical("Please increase the recursion limit of IssueFeatureSubgraph")
            return {
                "edit_patch": None,
                "passed_regression_test": False,
                "passed_reproducing_test": False,
                "passed_existing_test": False,
                "issue_response": "Failed to generate a feature implementation due to recursion limits.",
            }
        finally:
            self.container.cleanup()

        self._logger.info(f"Generated patch:\n{output_state['final_patch']}")
        self._logger.info("Feature implementation completed")

        # For feature requests, we don't have reproduction tests
        # We return the final patch as edit_patch to maintain compatibility with IssueState
        return {
            "edit_patch": output_state["final_patch"],
            "passed_regression_test": False,  # Will be updated based on actual test results
            "passed_reproducing_test": False,  # Not applicable for features
            "passed_existing_test": False,  # Not applicable in this simplified workflow
            "issue_response": "Feature implementation completed. Patch generated successfully.",
        }
