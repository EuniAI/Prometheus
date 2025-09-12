import logging
import threading
from typing import Dict

from langchain_core.messages import HumanMessage

from prometheus.utils.issue_util import format_issue_info


class IssueQuestionAnalyzerMessageNode:
    FIRST_HUMAN_PROMPT = """\
I am going to share details about an issue (Question) reported to a codebase and its related context.
Please analyze this question and provide a high-level response of the question:

1. Issue Understanding:
- Analyze the issue title, description, and comments provided

2. Answer the question through systematic investigation:
   - Identify which specific code elements are related to the question
   - Understand the context and interactions related to the question or issue

3. Provide high-level answer suggestions step by step

Here is a Github issue description:
-- BEGIN ISSUE --
{issue_info}
-- END ISSUE --
    
Here is the relevant code context and documentation needed to understand and answer this issue:
--- BEGIN CONTEXT --
{question_context}
--- END CONTEXT --
    
Based on the above information, please provide a detailed answer to the question.
"""

    def __init__(self):
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")

    def __call__(self, state: Dict):
        human_message = self.FIRST_HUMAN_PROMPT.format(
            issue_info=format_issue_info(
                state["issue_title"], state["issue_body"], state["issue_comments"]
            ),
            question_context="\n\n".join([str(context) for context in state["question_context"]]),
        )
        self._logger.debug(f"Sending message to IssueQuestionAnalyzerNode:\n{human_message}")
        return {"issue_question_analyzer_messages": [HumanMessage(human_message)]}
