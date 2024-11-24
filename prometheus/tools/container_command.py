from pydantic import BaseModel, Field

from prometheus.docker.general_container import GeneralContainer


class RunCommandInput(BaseModel):
  command: str = Field("The shell command to be run in the container")


RUN_COMMAND_DESCRIPTION = """\
Run a shell command in the container and return the result of the command. You are always at the root
of the codebase.
"""


def run_command(command: str, container: GeneralContainer) -> str:
  return container.execute_command(command)
