import logging
import threading
from typing import Dict

from langchain_core.messages import HumanMessage

from prometheus.utils.issue_util import format_issue_info


class IssueFeatureAnalyzerMessageNode:
    FIRST_HUMAN_PROMPT = """\
I am going to share details about a feature request reported to a codebase and its related context.
Please analyze this feature request and provide a high-level description of what needs to be implemented:

1. Feature Understanding:
- Analyze the feature request title, description, and comments provided
- Identify the desired functionality and requirements
- Clarify any ambiguities or edge cases

2. Architecture Analysis:
- Identify which files, modules, or components need to be created or modified
- Determine how this feature integrates with existing code
- Consider architectural patterns and conventions from the codebase

3. Implementation Plan:
For each needed change, describe in plain English:
- Which file needs to be created or modified
- Which classes, functions, or code blocks need to be added or changed
- What needs to be implemented (e.g., "add new method to handle X", "create new service class for Y")
- How this integrates with existing components

4. Considerations:
- Identify potential impacts on existing functionality
- Consider backward compatibility
- Note any dependencies or prerequisites

Do NOT provide actual code snippets or diffs. Focus on describing what needs to be implemented.

Here are the details for analysis:

{issue_info}

Feature Context:
{feature_context}
"""

    FOLLOWUP_HUMAN_PROMPT = """\
Given your suggestion, the edit agent generated the following patch:
{edit_patch}

The patch generated following error:
{edit_error}

Please analyze the failure and provide a revised implementation suggestion:

1. Error Analysis:
- Explain why the previous implementation failed
- Identify what specific aspects were problematic

2. Revised Implementation Suggestion:
Describe in plain English:
- Which file needs to be created or modified
- Which classes, functions, or code blocks need to be added or changed
- What needs to be implemented (e.g., "add new method to handle X", "create new service class for Y")
- Why this change would fix the error and properly implement the feature

Do NOT provide actual code snippets or diffs. Focus on describing what needs to be implemented.
"""

    def __init__(self):
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")

    def format_human_message(self, state: Dict):
        edit_error = ""
        if (
            "tested_patch_result" in state
            and state["tested_patch_result"]
            and not state["tested_patch_result"][0].passed
        ):
            edit_error = (
                f"The patch failed to pass the regression tests:\n"
                f"{state['tested_patch_result'][0].regression_test_failure_log}"
            )

        if not edit_error:
            return HumanMessage(
                self.FIRST_HUMAN_PROMPT.format(
                    issue_info=format_issue_info(
                        state["issue_title"], state["issue_body"], state["issue_comments"]
                    ),
                    feature_context="\n\n".join(
                        [str(context) for context in state["feature_context"]]
                    ),
                )
            )

        return HumanMessage(
            self.FOLLOWUP_HUMAN_PROMPT.format(
                edit_patch=state["edit_patch"],
                edit_error=edit_error,
            )
        )

    def __call__(self, state: Dict):
        human_message = self.format_human_message(state)
        self._logger.debug(f"Sending message to IssueFeatureAnalyzerNode:\n{human_message}")
        return {"issue_feature_analyzer_messages": [human_message]}
