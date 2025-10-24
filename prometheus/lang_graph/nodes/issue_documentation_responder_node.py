import logging
import threading

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from prometheus.lang_graph.subgraphs.issue_documentation_state import IssueDocumentationState
from prometheus.utils.issue_util import format_issue_info


class IssueDocumentationResponderNode:
    SYS_PROMPT = """\
You are a technical writer summarizing documentation updates for a GitHub issue.

Your task is to:
1. Review the documentation update request and the analysis/plan that was created
2. Review the patch that was generated
3. Create a clear, professional response explaining what documentation was updated

The response should:
- Summarize what documentation changes were made
- Explain how the changes address the issue request
- Be concise but informative
- Use a professional, helpful tone

Keep the response focused on what was accomplished, not implementation details.
"""

    USER_PROMPT = """\
Here is the documentation update request:
-- BEGIN ISSUE --
{issue_info}
-- END ISSUE --

Here is the analysis and plan that was created:
-- BEGIN PLAN --
{documentation_plan}
-- END PLAN --

Here is the patch with the documentation changes:
-- BEGIN PATCH --
{edit_patch}
-- END PATCH --

Please provide a clear, professional response summarizing the documentation updates for this issue.
"""

    def __init__(self, model: BaseChatModel):
        self.model = model
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")

    def __call__(self, state: IssueDocumentationState):
        from prometheus.utils.lang_graph_util import get_last_message_content

        documentation_plan = get_last_message_content(
            state["issue_documentation_analyzer_messages"]
        )

        user_message = self.USER_PROMPT.format(
            issue_info=format_issue_info(
                state["issue_title"], state["issue_body"], state["issue_comments"]
            ),
            documentation_plan=documentation_plan,
            edit_patch=state.get("edit_patch", "No changes were made."),
        )

        messages = [SystemMessage(self.SYS_PROMPT), HumanMessage(user_message)]
        response = self.model.invoke(messages)

        self._logger.info(f"Documentation update response:\n{response.content}")
        return {"issue_response": response.content}
