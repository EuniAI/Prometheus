import logging
import threading

from prometheus.docker.base_container import BaseContainer
from prometheus.lang_graph.subgraphs.run_existing_tests_state import RunExistingTestsState


class RunExistingTestsNode:
    """
    The node to execute existing tests commands in the container.
    """

    def __init__(self, container: BaseContainer):
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")
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
