import functools
import logging
import threading

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.tools import StructuredTool

from prometheus.lang_graph.subgraphs.issue_documentation_state import IssueDocumentationState
from prometheus.tools.web_search import WebSearchTool


class IssueDocumentationAnalyzerNode:
    SYS_PROMPT = """
You are an expert technical writer and software documentation specialist. Your role is to:

1. Carefully analyze documentation update requests by:
   - Understanding the issue description and what documentation changes are needed
   - Identifying which documentation files need to be created, updated, or modified
   - Understanding the context of existing documentation and source code

2. Create a comprehensive documentation plan through systematic analysis:
   - Identify specific documentation files that need changes
   - Determine what content needs to be added, updated, or removed
   - Ensure consistency with existing documentation style and structure
   - Consider the target audience and documentation purpose

3. Provide a clear, actionable plan that includes:
   - List of files to create, edit, or delete
   - Specific content changes for each file
   - Code examples, API references, or diagrams if needed
   - Recommendations for improving documentation clarity and completeness

Important:
- Keep descriptions precise and actionable
- Follow existing documentation conventions and style
- Ensure technical accuracy
- Only leave your direct final analysis and plan in the last response!

Your analysis should be thorough enough that an editor can implement the changes directly.
"""

    def __init__(self, model: BaseChatModel):
        self.system_prompt = SystemMessage(self.SYS_PROMPT)
        self.web_search_tool = WebSearchTool()
        self.tools = self._init_tools()
        self.model_with_tools = model.bind_tools(self.tools)

        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")

    def _init_tools(self):
        """Initializes tools for the node."""
        tools = []

        web_search_fn = functools.partial(self.web_search_tool.web_search)
        web_search_tool = StructuredTool.from_function(
            func=web_search_fn,
            name=self.web_search_tool.web_search.__name__,
            description=self.web_search_tool.web_search_spec.description,
            args_schema=self.web_search_tool.web_search_spec.input_schema,
        )
        tools.append(web_search_tool)

        return tools

    def __call__(self, state: IssueDocumentationState):
        message_history = [self.system_prompt] + state["issue_documentation_analyzer_messages"]
        response = self.model_with_tools.invoke(message_history)

        self._logger.debug(response)
        return {"issue_documentation_analyzer_messages": [response]}
