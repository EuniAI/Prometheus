import logging
import threading

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.lang_graph.subgraphs.context_retrieval_state import ContextRetrievalState
from prometheus.models.query import Query


class ContextRefineStructuredOutput(BaseModel):
    reasoning: str = Field(description="Your step by step reasoning.")
    query: str = Field(
        description="The main query to ask the ContextRetriever (one sentence). Empty if no additional context is needed."
    )
    extra_requirements: str = Field(
        default="",
        description="Optional additional requirements or fallback instructions (one sentence).",
    )
    purpose: str = Field(
        default="",
        description="Optional brief explanation of why this context is needed (one sentence).",
    )


class ContextRefineNode:
    SYS_PROMPT = """\
You are an intelligent assistant specialized in analyzing code context to determine if
additional source code or documentation from the codebase is necessary to fulfill the user's query.

Your goal is to request additional context ONLY when necessary:
1. When critical implementation details are missing to understand the current code
2. When key dependencies or related code are not visible in the current context
3. When documentation is needed to understand complex business logic, architecture, or requirements
4. When referenced files, classes, or functions are not included in the current context
5. When understanding the broader system context is essential for the task

DO NOT request additional context if:
1. The current context already contains sufficient information to complete the task
2. The additional context would only provide nice-to-have but non-essential details
3. The information is redundant with what's already available

Provide your analysis in a structured format matching the ContextRefineStructuredOutput model.

 Output Structure:
  - **query**: The main request for additional context (one sentence). Set to empty string "" if no additional context is needed.
  - **extra_requirements** (optional): Fallback instructions if the primary request cannot be fully satisfied.
  - **purpose** (optional): Brief explanation of why this context is needed and how it will help complete the task. Use when it helps clarify the intent.

Example output:
```json
{{
    "reasoning": "The current context lacks the test file content and shared test data definitions needed to extract the 8 relevant test cases.",
    "query": "Please provide the full content of sklearn/feature_extraction/tests/test_text.py",
    "extra_requirements": "If sending the full file is too large, please include at minimum: (a) the import statements at the top of the file, and (b) the definitions of ALL_FOOD_DOCS and JUNK_FOOD_DOCS, along with their line numbers.",
    "purpose": "I need to extract the 8 relevant test cases with their exact line numbers and include all necessary imports and shared test data."
}}
```

IMPORTANT: Keep all fields (query, extra_requirements, purpose) CONCISE and SHORT - ideally ONE sentence each.
PLEASE DO NOT INCLUDE ``` IN YOUR OUTPUT!
"""

    REFINE_PROMPT = """\
This is the codebase structure:
--- BEGIN FILE TREE ---
{file_tree}
--- END FILE TREE ---
    
This is the original user query:
--- BEGIN ORIGINAL QUERY ---
{original_query}
--- END ORIGINAL QUERY ---

All aggregated context for the queries:
--- BEGIN AGGREGATED CONTEXT ---
{context}
--- END AGGREGATED CONTEXT ---

Analyze if the current context is sufficient to complete the user query by considering:
1. Do you understand the full scope and requirements of the user query?
2. Do you have access to all relevant code that needs to be examined or modified?
3. Are all critical dependencies and their interfaces visible?
4. Is there enough context about the system architecture and design patterns?
5. Do you have access to relevant documentation or tests if needed?

Only request additional context if essential information is missing. Ensure you're not requesting:
- Information already provided in previous queries
- Nice-to-have but non-essential details
- Implementation details that aren't relevant to the current task

If additional context is needed:
- Be specific about what you're looking for
- Consider both code and documentation that might be relevant
"""

    def __init__(self, model: BaseChatModel, kg: KnowledgeGraph):
        self.file_tree = kg.get_file_tree()
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.SYS_PROMPT),
                ("human", "{human_prompt}"),
            ]
        )
        structured_llm = model.with_structured_output(ContextRefineStructuredOutput)
        self.model = prompt | structured_llm
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")

    def format_refine_message(self, state: ContextRetrievalState):
        original_query = state["query"]
        context = "\n\n".join([str(context) for context in state.get("context", [])])
        return self.REFINE_PROMPT.format(
            file_tree=self.file_tree,
            original_query=original_query,
            context=context,
        )

    def __call__(self, state: ContextRetrievalState):
        if "max_refined_query_loop" in state and state["max_refined_query_loop"] == 0:
            self._logger.info("Reached max_refined_query_loop, not asking for more context")
            return {"refined_query": None}

        # Format the human prompt
        human_prompt = self.format_refine_message(state)
        self._logger.debug(human_prompt)

        # Invoke the model
        response = self.model.invoke({"human_prompt": human_prompt})
        self._logger.debug(response)

        refined_query = Query(
            essential_query=response.query,
            extra_requirements=response.extra_requirements,
            purpose=response.purpose,
        )

        state_update = {"refined_query": refined_query}

        if "max_refined_query_loop" in state:
            state_update["max_refined_query_loop"] = state["max_refined_query_loop"] - 1

        return state_update
