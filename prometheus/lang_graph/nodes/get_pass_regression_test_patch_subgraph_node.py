import logging
import threading
from typing import Dict

from langchain_core.language_models.chat_models import BaseChatModel

from prometheus.docker.base_container import BaseContainer
from prometheus.git.git_repository import GitRepository
from prometheus.lang_graph.subgraphs.get_pass_regression_test_patch_subgraph import (
    GetPassRegressionTestPatchSubgraph,
)


class GetPassRegressionTestPatchSubgraphNode:
    def __init__(
        self,
        model: BaseChatModel,
        container: BaseContainer,
        git_repo: GitRepository,
        testing_patch_key: str,
        is_testing_patch_list: bool,
    ):
        self._logger = logging.getLogger(
            f"thread-{threading.get_ident()}.prometheus.lang_graph.nodes.get_pass_regression_test_patch_subgraph_node"
        )
        self.subgraph = GetPassRegressionTestPatchSubgraph(
            base_model=model,
            container=container,
            git_repo=git_repo,
        )
        self.testing_patch_key = testing_patch_key
        self.is_testing_patch_list = is_testing_patch_list

    def __call__(self, state: Dict):
        self._logger.info("Enter get_pass_regression_test_patch_subgraph_node")
        self._logger.debug(f"selected_regression_tests: {state['selected_regression_tests']}")

        output_state = self.subgraph.invoke(
            selected_regression_tests=state["selected_regression_tests"],
            patches=state[self.testing_patch_key]
            if self.is_testing_patch_list
            else [state[self.testing_patch_key]],
        )

        self._logger.debug(f"tested_patch_result: {output_state['tested_patch_result']}")

        return {
            "tested_patch_result": output_state["tested_patch_result"],
        }
