import functools
import logging
import threading

from langchain.tools import StructuredTool
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from prometheus.docker.base_container import BaseContainer
from prometheus.lang_graph.subgraphs.run_regression_tests_state import RunRegressionTestsState
from prometheus.tools.container_command import ContainerCommandTool


class RunRegressionTestsNode:
    SYS_PROMPT = """\
You are a agent that runs regression tests for a bug. Your role is to run all regression tests which have been provided to you and report the results accurately.

Your tasks are to:
1. Run all the exact regression tests which have been provided to you
2. If a command fails due to simple environment issues (like missing "./" prefix), make minimal adjustments to make it work
3. Report the exact output of the successful commands

Guidelines for command execution:
- Start by running the tests exactly as provided
- Test commands may be for DIFFERENT languages and test frameworks.
- If a command fails, you may make minimal adjustments like:
  * Adding "./" for executable files
  * Using appropriate path separators for the environment
  * Adding basic command prefixes if clearly needed (e.g., "python" for .py files)
  * If a tests command fails during the collection stage, you may use some args (e.g. --continue-on-collection-errors) to continue running the tests

CRITICAL RULES:
- You do NOT have to check if the tests exist or not. They are guaranteed to exist!
- Do NOT modify the core logic or parameters of the commands!
- Do NOT attempt to fix bugs or modify test logic!
- You MUST RUN ALL THE TESTS EXACTLY AS PROVIDED!
- Do NOT stop until all tests are run!
- DO NOT ASSUME ALL DEPENDENCIES ARE INSTALLED!

REMINDER:
- Install dependencies if needed!

Format your response as:
```
Result:
[exact output/result]
```

Remember: Your only job is to execute the commands and report results faithfully. Do not offer suggestions, analyze results, or try to fix issues.
"""

    HUMAN_PROMPT = """\
Selected Regression Tests:
{selected_regression_tests}
"""

    def __init__(self, model: BaseChatModel, container: BaseContainer):
        self.container_command_tool = ContainerCommandTool(container)
        self.tools = self._init_tools()
        self.model_with_tools = model.bind_tools(self.tools)
        self.system_prompt = SystemMessage(self.SYS_PROMPT)
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")

    def _init_tools(self):
        tools = []

        run_command_fn = functools.partial(self.container_command_tool.run_command)
        run_command_tool = StructuredTool.from_function(
            func=run_command_fn,
            name=self.container_command_tool.run_command.__name__,
            description=self.container_command_tool.run_command_spec.description,
            args_schema=self.container_command_tool.run_command_spec.input_schema,
        )
        tools.append(run_command_tool)

        return tools

    def format_human_message(self, state: RunRegressionTestsState) -> HumanMessage:
        return HumanMessage(
            self.HUMAN_PROMPT.format(
                selected_regression_tests="\n".join(state["selected_regression_tests"])
            )
        )

    def __call__(self, state: RunRegressionTestsState):
        human_message = self.format_human_message(state)
        message_history = [self.system_prompt, human_message] + state[
            "run_regression_tests_messages"
        ]

        response = self.model_with_tools.invoke(message_history)
        # Log the full response for debugging
        self._logger.debug(response)

        return {"run_regression_tests_messages": [response]}
