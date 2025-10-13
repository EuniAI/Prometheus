import logging
import threading
from typing import Dict

from langchain_core.messages import HumanMessage

from prometheus.utils.issue_util import format_issue_info
from prometheus.utils.lang_graph_util import get_last_message_content


class EditMessageNode:
    FIRST_HUMAN_PROMPT = """\
--- BEGIN ISSUE INFO ---
{issue_info}
--- END ISSUE INFO ---

Context Found:
--- BEGIN CONTEXT ---
{context}
--- END CONTEXT ---

Analyzer agent has analyzed the issue and provided instruction on the issue:
--- BEGIN ANALYZER MESSAGE ---
{analyzer_message}
--- END ANALYZER MESSAGE ---

Please implement these changes precisely, following the exact specifications from the analyzer.
"""

    FOLLOWUP_HUMAN_PROMPT = """\
The edit that you generated following error:
--- BEGIN EDIT ERROR ---
{edit_error}
--- END EDIT ERROR ---

Analyzer agent has analyzed the issue and provided instruction on the issue:
--- BEGIN ANALYZER MESSAGE ---
{analyzer_message}
--- END ANALYZER MESSAGE ---

Please implement these revised changes carefully, ensuring you address the specific issues that caused the previous error.
"""

    def __init__(self, context_key: str, analyzer_message_key: str):
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")
        self.context_key = context_key
        self.analyzer_message_key = analyzer_message_key

    def format_human_message(self, state: Dict):
        edit_error = ""
        if "reproducing_test_fail_log" in state and state["reproducing_test_fail_log"]:
            edit_error = f"Your failed to pass the bug exposing test cases:\n{state['reproducing_test_fail_log']}"
        elif "build_fail_log" in state and state["build_fail_log"]:
            edit_error = f"Your failed to pass the build:\n{state['build_fail_log']}"
        elif "existing_test_fail_log" in state and state["existing_test_fail_log"]:
            edit_error = f"Your failed to existing test cases:\n{state['existing_test_fail_log']}"

        if edit_error:
            return HumanMessage(
                self.FOLLOWUP_HUMAN_PROMPT.format(
                    edit_error=edit_error,
                    analyzer_message=get_last_message_content(state[self.analyzer_message_key]),
                )
            )

        return HumanMessage(
            self.FIRST_HUMAN_PROMPT.format(
                issue_info=format_issue_info(
                    state["issue_title"], state["issue_body"], state["issue_comments"]
                ),
                context="\n\n".join([str(context) for context in state[self.context_key]]),
                analyzer_message=get_last_message_content(state[self.analyzer_message_key]),
            )
        )

    def __call__(self, state: Dict):
        human_message = self.format_human_message(state)
        self._logger.debug(f"Sending message to EditNode:\n{human_message}")
        return {"edit_messages": [human_message]}
