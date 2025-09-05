import logging
import threading
from typing import Dict

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.errors import GraphRecursionError

from prometheus.docker.base_container import BaseContainer
from prometheus.lang_graph.subgraphs.run_regression_tests_subgraph import RunRegressionTestsSubgraph
from prometheus.utils.logger_manager import get_thread_logger


class RunRegressionTestsSubgraphNode:
    def __init__(
        self, model: BaseChatModel, container: BaseContainer, passed_regression_tests_key: str
    ):
        self._logger, file_handler = get_thread_logger(__name__)
        self.subgraph = RunRegressionTestsSubgraph(
            base_model=model,
            container=container,
        )
        self.passed_regression_tests_key = passed_regression_tests_key

    def __call__(self, state: Dict):
        self._logger.info("Enter run_regression_tests_subgraph_node")
        if not state["selected_regression_tests"]:
            self._logger.info("No regression tests selected, skipping regression tests subgraph.")
            return {
                self.passed_regression_tests_key: [],
                "regression_test_fail_log": "",
            }

        self._logger.debug(f"selected_regression_tests: {state['selected_regression_tests']}")

        try:
            output_state = self.subgraph.invoke(
                selected_regression_tests=state["selected_regression_tests"]
            )
        except GraphRecursionError as e:
            self._logger.error("Recursion Limit reached.")
            raise e

        self._logger.info(f"passed_regression_tests: {output_state['passed_regression_tests']}")
        self._logger.debug(f"regression_test_fail_log: {output_state['regression_test_fail_log']}")

        return {
            self.passed_regression_tests_key: output_state["passed_regression_tests"],
            "regression_test_fail_log": output_state["regression_test_fail_log"],
        }
