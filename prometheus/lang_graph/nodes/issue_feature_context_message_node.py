import logging
import threading
from typing import Dict

from prometheus.utils.issue_util import format_issue_info


class IssueFeatureContextMessageNode:
    FEATURE_QUERY = """\
{issue_info}

Find all relevant source code context and documentation needed to understand and implement this feature request.
Focus on production code (ignore test files) and follow these steps:
1. Identify similar existing features or components that this new feature should integrate with
2. Find relevant class definitions, interfaces, and API patterns used in the codebase
3. Locate related modules and services that the new feature will interact with
4. Include architectural patterns and code conventions used in similar implementations

Skip any test files
"""

    def __init__(self):
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")

    def __call__(self, state: Dict):
        feature_query = self.FEATURE_QUERY.format(
            issue_info=format_issue_info(
                state["issue_title"], state["issue_body"], state["issue_comments"]
            ),
        )
        self._logger.debug(f"Sending query to context provider:\n{feature_query}")
        return {"feature_query": feature_query}
