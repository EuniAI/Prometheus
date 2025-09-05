import logging
import threading

from prometheus.docker.base_container import BaseContainer
from prometheus.lang_graph.subgraphs.run_existing_tests_state import RunExistingTestsState
from prometheus.utils.logger_manager import get_thread_logger


class RunExistingTestsNode:
    """
    The node to execute existing tests commands in the container.
    """

    def __init__(self, container: BaseContainer):
        self._logger, file_handler = get_thread_logger(__name__)
        self.container = container

    def __call__(self, state: RunExistingTestsState):
        # Run the existing tests commands in the container
        output = self.container.run_test()

        # Log the output
        self._logger.info(f"Run existing tests output: {output}")

        # return the output
        return {
            "test_log": output,
        }
