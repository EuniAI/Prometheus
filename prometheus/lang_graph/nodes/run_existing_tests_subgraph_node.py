import logging
import threading
from typing import Dict

from langchain_core.language_models.chat_models import BaseChatModel

from prometheus.docker.base_container import BaseContainer
from prometheus.git.git_repository import GitRepository
from prometheus.lang_graph.subgraphs.run_existing_tests_subgraph import RunExistingTestsSubgraph


class RunExistingTestsSubgraphNode:
    def __init__(
        self,
        model: BaseChatModel,
        container: BaseContainer,
        git_repo: GitRepository,
        testing_patch_key: str,
        existing_test_fail_log_key: str,
    ):
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")
        self.subgraph = RunExistingTestsSubgraph(
            base_model=model, container=container, git_repo=git_repo
        )
        self.git_repo = git_repo
        self.testing_patch_key = testing_patch_key
        self.existing_test_fail_log_key = existing_test_fail_log_key

    def __call__(self, state: Dict):
        self._logger.info("Enter run_existing_tests_subgraph_node")

        try:
            output_state = self.subgraph.invoke(testing_patch=state[self.testing_patch_key])
        finally:
            self.git_repo.reset_repository()

        self._logger.debug(output_state["test_fail_log"])

        return {
            self.existing_test_fail_log_key: output_state["test_fail_log"],
        }
