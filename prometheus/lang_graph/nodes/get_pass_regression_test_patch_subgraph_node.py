import logging
import threading
from typing import Dict

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.errors import GraphRecursionError

from prometheus.docker.base_container import BaseContainer
from prometheus.git.git_repository import GitRepository
from prometheus.lang_graph.subgraphs.get_pass_regression_test_patch_subgraph import (
    GetPassRegressionTestPatchSubgraph,
)
from prometheus.models.test_patch_result import TestedPatchResult


class GetPassRegressionTestPatchSubgraphNode:
    def __init__(
        self,
        base_model: BaseChatModel,
        advanced_model: BaseChatModel,
        container: BaseContainer,
        git_repo: GitRepository,
        testing_patch_key: str,
        is_testing_patch_list: bool,
        return_str_patch: bool,
        return_key: str,
    ):
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")
        self.subgraph = GetPassRegressionTestPatchSubgraph(
            base_model=base_model,
            advanced_model=advanced_model,
            container=container,
            git_repo=git_repo,
        )
        self.git_repo = git_repo
        self.testing_patch_key = testing_patch_key
        self.is_testing_patch_list = is_testing_patch_list
        self.return_str_patch = return_str_patch
        self.return_key = return_key

    def __call__(self, state: Dict):
        self._logger.info("Enter get_pass_regression_test_patch_subgraph_node")
        self._logger.debug(f"selected_regression_tests: {state['selected_regression_tests']}")

        testing_patch = (
            state[self.testing_patch_key]
            if self.is_testing_patch_list
            else [state[self.testing_patch_key]]
        )

        if not state["selected_regression_tests"]:
            self._logger.info("No regression tests selected, skipping patch testing.")

            test_patch_results = [
                TestedPatchResult(patch=patch, passed=True, regression_test_failure_log="")
                for patch in testing_patch
            ]
        else:
            try:
                output_state = self.subgraph.invoke(
                    selected_regression_tests=state["selected_regression_tests"],
                    patches=testing_patch,
                )
                self._logger.debug(f"tested_patch_result: {output_state['tested_patch_result']}")
                test_patch_results = output_state["tested_patch_result"]
            except GraphRecursionError:
                # If the recursion limit is reached, return a failure result for each patch
                self._logger.info("Recursion limit reached")
                test_patch_results = [
                    TestedPatchResult(
                        patch=patch,
                        passed=False,
                        regression_test_failure_log="Fail to get regression test result. Please try again!",
                    )
                    for patch in testing_patch
                ]

            finally:
                # Reset the git repository to its original state
                self.git_repo.reset_repository()

        return {
            self.return_key: [result.patch for result in test_patch_results if result.passed]
            if self.return_str_patch
            else test_patch_results,
        }
