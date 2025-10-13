import logging
import threading
from typing import Dict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from prometheus.utils.issue_util import format_issue_info


class IssueFeatureResponderNode:
    SYS_PROMPT = """\
You are the final agent in a multi-agent feature implementation system. Users request features on GitHub/GitLab, and our system works to implement them.
Your role is to compose the response that will be posted back to the issue thread.

The information you receive is structured as follows:
- Issue Information (from user): The original feature request title, body, and any user comments
- Final patch: Created by our implementation agent to add the requested feature
- Verification: Results from our testing agent confirming the implementation works

Write a clear, professional response that will be posted directly as a comment. Your response should:
- Be concise yet informative
- Use a professional and friendly tone appropriate for open source communication
- Acknowledge the feature request
- Explain the implemented solution (from patch)
- Include any successful verification results if available
- Note that this is an initial implementation that may require refinement

Avoid:
- Mentioning that you are an AI or part of an automated system
- Using overly formal or robotic language
- Making assumptions beyond what our agents have provided
- Promising future enhancements or making commitments
- Claiming the implementation is perfect or complete

Format your response as a properly structured comment.
"""

    HUMAN_PROMPT = """\
{issue_info}

Generated patch:
{final_patch}

Verification:
{verification}
"""

    def __init__(self, model: BaseChatModel):
        self.system_prompt = SystemMessage(self.SYS_PROMPT)
        self.model = model

        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")

    def format_human_message(self, state: Dict) -> HumanMessage:
        verification_messages = []

        # Check if regression tests were run and passed
        if state.get("run_regression_test", False):
            # Check if tested_patch_result exists and has results with at least one passing test
            if state.get("selected_regression_tests", []):
                verification_messages.append("✓ All selected regression tests passed successfully")

        # Build verification summary
        if verification_messages:
            verification_summary = "\n".join(verification_messages)
        else:
            verification_summary = "No automated tests were run for this feature implementation."

        formatted_message = self.HUMAN_PROMPT.format(
            issue_info=format_issue_info(
                state["issue_title"], state["issue_body"], state["issue_comments"]
            ),
            final_patch=state.get("final_patch", "No patch was generated."),
            verification=verification_summary,
        )

        return HumanMessage(content=formatted_message)

    def __call__(self, state: Dict):
        messages = [
            self.system_prompt,
            self.format_human_message(state),
        ]
        response = self.model.invoke(messages)
        self._logger.debug(response)
        return {"issue_response": response.content}
