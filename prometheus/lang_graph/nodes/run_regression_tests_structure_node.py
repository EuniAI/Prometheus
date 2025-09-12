import logging
import threading
from typing import Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from prometheus.lang_graph.subgraphs.run_regression_tests_state import RunRegressionTestsState
from prometheus.utils.lang_graph_util import get_last_message_content


class RunRegressionTestsStructureOutput(BaseModel):
    passed_regression_tests: Sequence[str] = Field(
        description="List of test identifier of regression tests that passed (e.g., class name and method name)"
    )
    regression_test_fail_log: str = Field(
        description="Complete failure log if any test failed. Empty string if all tests passed or no tests were run."
    )
    total_tests_run: int = Field(
        description="Total number of tests run, including both passed and failed tests, or 0 if no tests were run",
        default=0,
    )


class RunRegressionTestsStructuredNode:
    SYS_PROMPT = """\
You are a test result parser. Your only task is to check if the executed tests passed.

Your task is to:
1. Check which sets of tests passes by looking for test pass indicators:
   - Test summary showing "passed" or "PASSED"
   - Warning is ok
   - No "FAILURES" section
2. If ANY test failed, capture the complete failure output; otherwise leave failure log empty
3. Return the exact test identifiers that passed
4. Count the total number of tests run. Only count tests that were actually executed (Both Passed and Failed)! Regardless of pass or fail, count them if they were run.

Return:
- passed_regression_tests: List of test identifier of regression tests that passed (e.g., class name and method name)
- regression_test_fail_log: empty string if all tests pass, exact complete test output if a test fails
- total_tests_run: Total number of tests run, including BOTH PASSED and FAILED tests. If you can't find any test run, return 0

Example 1:

<example>
```
Run Regression Tests Logs:
============================= test session starts ==============================
collected 6 items

test_patch_util.py::test_get_updated_files_empty_diff PASSED             [ 16%]
test_patch_util.py::test_get_updated_files_added_only FAILED             [ 33%]
tests/utils/test_patch_util.py:13 (test_get_updated_files_added_only)
0 != 1

Expected:1
Actual:0
<点击以查看差异>

def test_get_updated_files_added_only():
        diff = \"""
    diff --git a/new_file.txt b/new_file.txt
    new file mode 100644
    index 0000000..1234567
    --- /dev/null
    +++ b/new_file.txt
    @@ -0,0 +1 @@
    +New content
    \"""
        added, modified, removed = get_updated_files(diff)
        assert len(added) == 1
>       assert len(modified) == 1
E       assert 0 == 1
E        +  where 0 = len([])

test_patch_util.py:26: AssertionError

test_patch_util.py::test_get_updated_files_modified_only PASSED          [ 50%]
test_patch_util.py::test_get_updated_files_removed_only PASSED           [ 66%]
test_patch_util.py::test_get_updated_files_multiple_changes PASSED       [ 83%]
test_patch_util.py::test_get_updated_files_with_subfolders PASSED        [100%]

========================= 1 failed, 5 passed in 0.03s ==========================
```

Example 1 Output:
{{  
    "passed_regression_tests": [
        "test_patch_util.py::test_get_updated_files_empty_diff",
        "test_patch_util.py::test_get_updated_files_modified_only",
        "test_patch_util.py::test_get_updated_files_removed_only",
        "test_patch_util.py::test_get_updated_files_multiple_changes",
        "test_patch_util.py::test_get_updated_files_with_subfolders"
    ],
    "regression_test_fail_log": "test_patch_util.py::test_get_updated_files_added_only FAILED             [ 33%] tests/utils/test_patch_util.py:13 (test_get_updated_files_added_only) 0 != 1 Expected:1 Actual:0 <点击以查看差异> def test_get_updated_files_added_only():         diff = \\\"\"\"     diff --git a/new_file.txt b/new_file.txt     new file mode 100644     index 0000000..1234567     --- /dev/null     +++ b/new_file.txt     @@ -0,0 +1 @@     +New content     \\\"\"\"         added, modified, removed = get_updated_files(diff)         assert len(added) == 1 >       assert len(modified) == 1 E       assert 0 == 1 E        +  where 0 = len([]) test_patch_util.py:26: AssertionError",
    "total_tests_run": 6
}}
</example>

Important:
- Only look at test pass/fail status
- A single failing test means the test is not passing
- Include complete test output in failure log
- Do Not output any log when where is no test executed. ONLY output the log exact and complete test FAILURE log when test failure!
- Only include tests that actually executed (Both Passed and Failed). If tests couldn't run due to setup errors, don't count them.
- If you can't find any test run, return 0 for total number of tests run!
"""
    HUMAN_PROMPT = """
We have run the selected regression tests on the codebase.
The following regression tests were selected to run:
--- BEGIN SELECTED REGRESSION TESTS ---
{selected_regression_tests}
--- END SELECTED REGRESSION TESTS ---

Run Regression Tests Logs:
--- BEGIN LOG ---
{run_regression_tests_messages}
--- END LOG ---

Please analyze the logs and determine which regression tests passed!. You should return the exact test identifier 
that we give to you.
Don't forget to return the total number of tests run!
"""

    def __init__(self, model: BaseChatModel):
        prompt = ChatPromptTemplate.from_messages(
            [("system", self.SYS_PROMPT), ("human", "{human_message}")]
        )
        structured_llm = model.with_structured_output(RunRegressionTestsStructureOutput)
        self.model = prompt | structured_llm
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")

    def get_human_message(self, state: RunRegressionTestsState) -> str:
        # Format the human message using the state
        return self.HUMAN_PROMPT.format(
            selected_regression_tests="\n".join(state["selected_regression_tests"]),
            run_regression_tests_messages=get_last_message_content(
                state["run_regression_tests_messages"]
            ),
        )

    def __call__(self, state: RunRegressionTestsState):
        # Get human message from the state
        human_message = self.get_human_message(state)
        self._logger.debug(f"Human Message: {human_message}")
        response = self.model.invoke({"human_message": human_message})
        # Log the full response for debugging
        self._logger.debug(response)
        return {
            "regression_test_fail_log": response.regression_test_fail_log,
            "passed_regression_tests": response.passed_regression_tests,
            "total_tests_run": response.total_tests_run,
        }
