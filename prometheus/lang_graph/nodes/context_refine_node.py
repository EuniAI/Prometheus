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

When generating new queries, please review the previous queries to AVOID asking for the SAME or very similar information.
Try to explore DIFFERENT aspects of the codebase rather than repeating similar requests, as these queries have already been asked and satisfied.
ONLY generate queries about the codebase! Execution traces, error logs, or non-code information are out of scope!

Record your decision by calling the structured-output tool with these fields:
  - reasoning: Your step-by-step reasoning about whether more context is needed and why.
  - query: The main request for additional context (one sentence). Set to an empty string "" if no additional context is needed.
  - extra_requirements (optional): Fallback instructions if the primary request cannot be fully satisfied.
  - purpose (optional): Brief explanation of why this context is needed and how it will help complete the task.

Example: when the test file content and shared test-data definitions are missing, set query to
"Please provide the full content of sklearn/feature_extraction/tests/test_text.py"; set extra_requirements to
ask for at least the import statements and the ALL_FOOD_DOCS / JUNK_FOOD_DOCS definitions with their line
numbers if the file is too large; set purpose to explain you need to extract the relevant test cases with their
exact line numbers.

Example: when only helper-function implementations and data-processing documentation are missing, set query to
"Please provide the implementation details of the helper functions called within the main function, as well as
any relevant documentation that explains the overall data processing workflow", and leave extra_requirements
and purpose empty.

IMPORTANT: Keep all fields (query, extra_requirements, purpose) CONCISE and SHORT - ideally ONE sentence each.

HOW TO RESPOND:
- You MUST answer by calling the `ContextRefineStructuredOutput` tool with its arguments (reasoning, query, extra_requirements, purpose).
- Calling the tool is your ONLY way to respond. Do NOT reply with a normal assistant message, an explanation, or raw JSON text.
- Always emit exactly one tool call (set query to "" when no more context is needed).
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

{previous_queries}

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

IMPORTANT:
- Try to avoid asking for the SAME or very similar information as previous queries, because these queries have already been asked and satisfied.
"""

    def __init__(self, model: BaseChatModel, kg: KnowledgeGraph):
        self.file_tree = kg.get_file_tree()
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.SYS_PROMPT),
                ("human", "{human_prompt}"),
            ]
        )
        structured_llm = model.with_structured_output(ContextRefineStructuredOutput).with_retry()
        self.model = prompt | structured_llm
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")

    def format_refine_message(self, state: ContextRetrievalState):
        original_query = state["query"]
        context = "\n\n".join([str(context) for context in state.get("context", [])])

        # Include previous refined queries if available
        previous_refined_queries = state.get("previous_refined_queries", [])
        if previous_refined_queries:
            previous_queries = "\n\n".join(
                [
                    f"Previous refined query {i + 1}:\nEssential Query: {q.essential_query}\n"
                    f"Extra Requirements: {q.extra_requirements}\nPurpose: {q.purpose}"
                    for i, q in enumerate(previous_refined_queries)
                ]
            )
            previous_queries = f"These are the previously asked refined queries:\n--- BEGIN PREVIOUS QUERY ---\n{previous_queries}\n--- END PREVIOUS QUERY ---"
        else:
            previous_queries = ""

        # Format the refine prompt
        return self.REFINE_PROMPT.format(
            file_tree=self.file_tree,
            original_query=original_query,
            context=context,
            previous_queries=previous_queries,
        )

    def __call__(self, state: ContextRetrievalState):
        if state["max_refined_query_loop"] == 0:
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

        state_update = {
            "refined_query": refined_query,
            "max_refined_query_loop": state["max_refined_query_loop"] - 1,
        }
        return state_update
