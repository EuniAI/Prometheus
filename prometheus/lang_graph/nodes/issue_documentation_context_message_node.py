import logging
import threading

from prometheus.lang_graph.subgraphs.issue_documentation_state import IssueDocumentationState
from prometheus.utils.issue_util import format_issue_info


class IssueDocumentationContextMessageNode:
    DOCUMENTATION_QUERY = """\
{issue_info}

Find all relevant documentation files and source code context needed to update the documentation according to this issue.
Focus on:
1. Existing documentation files (README.md, docs/, etc.)
2. Source code that needs to be documented or referenced
3. Related configuration files or examples
4. Any existing documentation that needs to be updated or extended

Include both documentation files and relevant source code context.
"""

    def __init__(self):
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")

    def __call__(self, state: IssueDocumentationState):
        documentation_query = self.DOCUMENTATION_QUERY.format(
            issue_info=format_issue_info(
                state["issue_title"], state["issue_body"], state["issue_comments"]
            ),
        )
        self._logger.debug(f"Sending query to context provider:\n{documentation_query}")
        return {"documentation_query": documentation_query}
