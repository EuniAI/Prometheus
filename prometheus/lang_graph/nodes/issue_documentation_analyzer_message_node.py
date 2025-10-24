import logging
import threading

from langchain_core.messages import HumanMessage

from prometheus.lang_graph.subgraphs.issue_documentation_state import IssueDocumentationState
from prometheus.utils.issue_util import format_issue_info


class IssueDocumentationAnalyzerMessageNode:
    FIRST_HUMAN_PROMPT = """\
I am going to share details about a documentation update request and its related context.
Please analyze this request and provide a detailed plan for updating the documentation:

1. Issue Understanding:
- Analyze the issue title, description, and comments to understand what documentation needs to be updated
- Identify the type of documentation change (new documentation, updates, fixes, improvements)

2. Context Analysis:
- Review the retrieved documentation files and source code context
- Identify which files need to be modified, created, or updated
- Understand the current documentation structure and style

3. Documentation Plan:
- Provide a step-by-step plan for updating the documentation
- Specify which files to create, edit, or delete
- Describe what content needs to be added or changed
- Ensure consistency with existing documentation style
- Include any code examples, API references, or diagrams if needed

Here is the documentation update request:
-- BEGIN ISSUE --
{issue_info}
-- END ISSUE --

Here is the relevant context (existing documentation and source code):
--- BEGIN CONTEXT --
{documentation_context}
--- END CONTEXT --

Based on the above information, please provide a detailed analysis and plan for updating the documentation.
"""

    def __init__(self):
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")

    def __call__(self, state: IssueDocumentationState):
        human_message = self.FIRST_HUMAN_PROMPT.format(
            issue_info=format_issue_info(
                state["issue_title"], state["issue_body"], state["issue_comments"]
            ),
            documentation_context="\n\n".join(
                [str(context) for context in state["documentation_context"]]
            ),
        )
        self._logger.debug(f"Sending message to IssueDocumentationAnalyzerNode:\n{human_message}")
        return {"issue_documentation_analyzer_messages": [HumanMessage(human_message)]}
