import logging
import threading

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from prometheus.lang_graph.subgraphs.run_existing_tests_state import RunExistingTestsState
from prometheus.utils.logger_manager import get_thread_logger


class RunExistingTestsStructureOutput(BaseModel):
    success: bool


class RunExistingTestsStructuredNode:
    SYS_PROMPT = """\
You are a test result parser. Your only task is to determine if all the executed tests passed successfully.

Your task is to:
1. Analyze the test execution logs
2. Look for test result indicators:
   - Test summary showing "passed" or "PASSED" 
   - Check for "FAILURES" or "FAILED" sections
   - Check for error messages or exceptions
   - Warning messages are acceptable and don't indicate failure
3. Determine overall success status

Return:
- success: True if ALL tests passed successfully, False if ANY test failed

Important rules:
- Even a single test failure means overall success is False
- If tests couldn't run due to errors (e.g., import errors, syntax errors), return False
- Warnings alone don't constitute failure
- Empty test runs or no tests found should return False
- Look for clear pass/fail indicators in the test framework output
"""

    HUMAN_PROMPT = """\
We have run the existing tests on the codebase.

Test Execution Logs:
--- BEGIN LOG ---
{test_log}
--- END LOG ---

Please analyze the logs and determine if all tests passed successfully.
Return True only if ALL tests passed without any failures.
Return False if ANY test failed or if tests couldn't run properly.
"""

    def __init__(self, model: BaseChatModel):
        prompt = ChatPromptTemplate.from_messages(
            [("system", self.SYS_PROMPT), ("human", "{human_message}")]
        )
        structured_llm = model.with_structured_output(RunExistingTestsStructureOutput)
        self.model = prompt | structured_llm
        self._logger, file_handler = get_thread_logger(__name__)

    def __call__(self, state: RunExistingTestsState):
        # Get human message from the state
        human_message = self.HUMAN_PROMPT.format(test_log=state["test_log"])
        self._logger.debug(f"Human Message: {human_message}")

        # Invoke the model
        response = self.model.invoke({"human_message": human_message})

        # Log the full response for debugging
        self._logger.debug(response)

        # return the response
        return {
            "success": response.success,
        }
