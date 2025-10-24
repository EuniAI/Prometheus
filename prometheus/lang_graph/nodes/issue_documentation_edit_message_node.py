import logging
import threading

from langchain_core.messages import HumanMessage

from prometheus.lang_graph.subgraphs.issue_documentation_state import IssueDocumentationState
from prometheus.utils.lang_graph_util import get_last_message_content


class IssueDocumentationEditMessageNode:
    EDIT_PROMPT = """\
Based on the following documentation analysis and plan, please implement the documentation changes using the available file operation tools.

Documentation Analysis and Plan:
--- BEGIN PLAN ---
{documentation_plan}
--- END PLAN ---

Context Collected:
--- BEGIN CONTEXT --
{documentation_context}
--- END CONTEXT --

Please proceed to implement the documentation changes:
1. Read existing files first to understand the current state
2. Make precise edits that preserve existing formatting and style
3. Create new files if specified in the plan
4. Verify your changes by reading the files again after editing
5. Follow the documentation style and conventions observed in the existing documentation

Remember:
- Follow the plan provided in the analysis
- Maintain consistency with existing documentation style
- Ensure all edits are precise and accurate
"""

    def __init__(self):
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")

    def __call__(self, state: IssueDocumentationState):
        documentation_plan = get_last_message_content(
            state["issue_documentation_analyzer_messages"]
        )
        documentation_context = "\n\n".join(
            [str(context) for context in state["documentation_context"]]
        )
        human_message = self.EDIT_PROMPT.format(
            documentation_plan=documentation_plan, documentation_context=documentation_context
        )
        self._logger.debug(f"Sending message to EditNode:\n{human_message}")
        return {"edit_messages": [HumanMessage(human_message)]}
