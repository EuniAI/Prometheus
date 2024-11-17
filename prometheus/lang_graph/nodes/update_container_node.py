"""Container synchronization handler for agent-made changes.

This module provides functionality to synchronize file changes made by AI agents
with a container environment. It ensures that any modifications made to the project
files are properly reflected in the container's filesystem, maintaining consistency
between the agent's workspace and the container environment.
"""

import logging

from prometheus.docker.base_container import BaseContainer
from prometheus.lang_graph.subgraphs.issue_answer_and_fix_state import IssueAnswerAndFixState


class UpdateContainerNode:
  """Synchronizes agent-made changes with container filesystem.

  This class handles the synchronization of file changes between an agent's
  workspace and a container environment. It ensures that any modifications
  made by AI agents (such as code fixes or edits) are properly reflected
  in the container where builds, tests, or other operations may occur.
  """

  def __init__(self, container: BaseContainer):
    """Initializes the UpdateContainerNode with a target container.

    Args:
      container: Container instance that will receive file updates. Must
        be a subclass of BaseContainer implementing the update_files method.
    """
    self.container = container
    self._logger = logging.getLogger("prometheus.lang_graph.nodes.update_container_node")

  def __call__(self, state: IssueAnswerAndFixState):
    """Synchronizes the current project state with the container."""
    if self.container.container is not None:
      self.container.update_files(new_project_path=state["project_path"])
    else:
      self._logger.info(
        "Not updating files in docker container because it is not running, "
        "most likely due to run_build and run_test are both false."
      )
