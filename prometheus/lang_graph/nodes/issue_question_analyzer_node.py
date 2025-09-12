import functools

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.tools import StructuredTool

from prometheus.lang_graph.subgraphs.issue_question_state import IssueQuestionState
from prometheus.tools.web_search import WebSearchTool
from prometheus.utils.logger_manager import get_thread_logger


class IssueQuestionAnalyzerNode:
    SYS_PROMPT = """
You are an expert software engineer specializing in analysis and answering issue. Your role is to:

1. Carefully analyze reported software issues and question by:
   - Understanding issue descriptions and symptoms
   - Identifying related code components

2. Answer the question through systematic investigation:
   - Identify which specific code elements are related to the question
   - Understand the context and interactions related to the question or issue

3. Provide high-level answer suggestions step by step

Important:
- You may provide actual code snippets or diffs if necessary
- Keep descriptions precise and actionable

Communicate in a clear, technical manner focused on accurate analysis and practical suggestions
rather than implementation details.
"""

    def __init__(self, model: BaseChatModel):
        self.system_prompt = SystemMessage(self.SYS_PROMPT)
        self.web_search_tool = WebSearchTool()
        self.tools = self._init_tools()
        self.model_with_tools = model.bind_tools(self.tools)

        self._logger, file_handler = get_thread_logger(__name__)

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

    def __call__(self, state: IssueQuestionState):
        message_history = [self.system_prompt] + state["issue_question_analyzer_messages"]
        response = self.model_with_tools.invoke(message_history)

        self._logger.debug(response)
        return {"issue_question_analyzer_messages": [response]}
