import functools
import logging
import threading

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.tools import StructuredTool

from prometheus.lang_graph.subgraphs.issue_question_state import IssueQuestionState
from prometheus.tools.web_search import WebSearchTool


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
- Only leave your direct final answer in the last response! Do NOT include any simple issue's understanding and analysis in the final answer.

Communicate in a clear, technical manner focused on accurate analysis and practical suggestions
rather than implementation details.

--- BEGIN EXAMPLE ---
Issue title:
Please tell me what this project about?

Issue description: 
Please tell me what this project about?

Issue comments:

Context:
.......

--- BEGIN EXAMPLE FINAL ANSWER ---
- What the project is:
  - Astropy is the core Python library for astronomy and astrophysics. It provides standardized, high-quality building blocks......
  
- Key capabilities (non-exhaustive):
  - Units and physical/astronomical constants: astropy.units, astropy.constants (with configurable standards such as CODATA and IAU).
  - Coordinates and time: astropy.coordinates for celestial coordinates and frames; astropy.time for time scales, precision time handling.
  - Tables and I/O: astropy.table for structured data; astropy.io for reading/writing many astronomy data formats (e.g., FITS via astropy.io.fits).
  - WCS: astropy.wcs for World Coordinate System transformations in images.
  - Modeling and fitting: astropy.modeling for models, parameter fitting, and compound models.
  - Cosmology: astropy.cosmology for cosmological models and calculations.
  - Statistics, visualization, convolution, time series, uncertainties, and more: astropy.stats, astropy.visualization.......

- How to install:
  - pip install astropy
  - Full instructions: https://docs.astropy.org/en/stable/install.html

- Where to learn more:
  - Website: https://astropy.org/
  - Documentation: https://docs.astropy.org/
  - Getting started and tutorials: https://learn.astropy.org
  - Ecosystem and affiliated packages: https://www.astropy.org/affiliated/
  - Community/help: Slack (https://astropy.slack.com/), Discourse (https://community.openastronomy.org/c/astropy/8), mailing lists (links in README).

- Citing and license:
  - Citation/acknowledgement guidance: https://www.astropy.org/acknowledging.html
  - License: 3-clause BSD (LICENSE.rst)

- Suggested maintainer response/actions:
  - Reply with the concise summary above and the key links (Website, Docs, Install, Learn, Affiliated packages).
  - Optionally point the reporter to community channels if they have follow-up usage questions.
  - If the question is answered, label as “question” and close the issue after confirming with the reporter.
--- END EXAMPLE FINAL ANSWER ---

--- END EXAMPLE ---

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

    def __call__(self, state: IssueQuestionState):
        message_history = [self.system_prompt] + state["issue_question_analyzer_messages"]
        response = self.model_with_tools.invoke(message_history)

        self._logger.debug(response)
        return {"issue_question_analyzer_messages": [response]}
