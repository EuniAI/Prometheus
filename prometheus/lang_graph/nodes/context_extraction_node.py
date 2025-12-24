import logging
import threading
from typing import Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from prometheus.exceptions.file_operation_exception import FileOperationException
from prometheus.lang_graph.subgraphs.context_retrieval_state import ContextRetrievalState
from prometheus.models.context import Context
from prometheus.utils.file_utils import read_file_with_line_numbers
from prometheus.utils.knowledge_graph_utils import deduplicate_contexts

SYS_PROMPT = """\
You are a context summary agent that summarizes code contexts which is relevant to a given query.
 Your goal is to extract, evaluate and summary code contexts that directly answers the query requirements.

Your evaluation and summarization must consider two key aspects:
1. Query Match: Which set of contexts directly address specific requirements mentioned in the query?
2. Extended relevance: Which set of contexts provide essential information needed to understand the query topic?

Follow these strict evaluation steps:
1. First, identify specific requirements in the query
2. Check which set of contexts directly addresses these requirements
3. Check which parts of code contexts are relevant to the query
4. Consider if they provides essential context by examining:
   - Function dependencies
   - Type definitions
   - Configuration requirements
   - Implementation details needed for completeness

Query relevance guidelines - include only if:
- It directly implements functionality mentioned in the query
- It contains specific elements the query asks about
- It's necessary to understand or implement query requirements
- It provides critical information needed to answer the query

CRITICAL RULE:
- You don't have to select whole piece of code that you have seen, ONLY select the parts that are relevant to the query.
- Each context MUST be SHORT and CONCISE, focusing ONLY on the lines that are relevant to the query.
- Several contexts can be extracted from the same file, but each context must be concise and relevant to the query.
- Do NOT include any irrelevant lines or comments that do not contribute to answering the query.
- Do NOT include same context multiple times.

Remember: Your primary goal is to summarize contexts that directly helps answer the query requirements.

Provide your analysis in a structured format matching the ContextExtractionStructuredOutput model.

Example output 1:
```json
{{
    "context": [{{
        "reasoning": "1. Query requirement analysis:\n   - Query specifically asks about password validation\n   - Context provides implementation details for password validation\n2. Extended relevance:\n   - This function is essential for understanding how passwords are validated in the system",
        "relative_path": "pychemia/code/fireball/fireball.py",
        "start_line": 270, # Must be greater than or equal to 1
        "end_line": 293 # Must be greater than or equal to start_line
    }} ......]
}}
```
Example output 2 (No relevant context):
```json
{{
    "context": []
}}
```

Your task is to summarize the relevant contexts to a given query and return it in the specified format.
ALL fields are required!
"""

HUMAN_MESSAGE = """\
This is the query you need to answer:

--- BEGIN QUERY ---
{query}
--- END QUERY ---

{extra_requirements}

{purpose}

The context or file content that you have seen so far (Some of the context may be IRRELEVANT to the query!!!):

--- BEGIN CONTEXT ---
{context}
--- END CONTEXT ---

Example output 1:
```json
{{
    "context": [{{
        "reasoning": "1. Query requirement analysis:\n   - Query specifically asks about password validation\n   - Context provides implementation details for password validation\n2. Extended relevance:\n   - This function is essential for understanding how passwords are validated in the system",
        "relative_path": "pychemia/code/fireball/fireball.py",
        "start_line": 270, # Must be greater than or equal to 1
        "end_line": 293 # Must be greater than or equal to start_line
    }} ......]
}}
```
Example output 2 (No relevant context):
```json
{{
    "context": []
}}
```

REMEMBER: Your task is to summarize the relevant contexts to the given query and return it in the specified format!
ALL fields are required!
"""


class ContextOutput(BaseModel):
    reasoning: str = Field(
        description="Your step-by-step reasoning why the context is relevant to the query"
    )
    relative_path: str = Field(description="Relative path to the context file in the codebase")
    start_line: int = Field(
        description="Start line number of the context in the file, minimum is 1"
    )
    end_line: int = Field(
        description="End line number of the context in the file, minimum is 1. "
        "The Content in the end line is including"
    )


class ContextExtractionStructuredOutput(BaseModel):
    context: Sequence[ContextOutput] = Field(
        description="List of contexts extracted from the history messages. "
        "Each context must have a reasoning, relative path, start line and end line."
    )


class ContextExtractionNode:
    def __init__(self, model: BaseChatModel, root_path: str):
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYS_PROMPT),
                ("human", "{human_prompt}"),
            ]
        )
        structured_llm = model.with_structured_output(ContextExtractionStructuredOutput).with_retry(stop_after_attempt=5)
        self.model = prompt | structured_llm
        self.root_path = root_path
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")

    def format_human_message(self, state: ContextRetrievalState):
        refined_query = state["refined_query"]
        explored_context = state["explored_context"]

        query_str = refined_query.essential_query
        extra_requirements_str = (
            f"--- BEGIN EXTRA REQUIREMENTS ---\n{refined_query.extra_requirements}\n--- END EXTRA REQUIREMENTS ---"
            if refined_query.extra_requirements
            else ""
        )
        purpose_str = (
            f"--- BEGIN PURPOSE ---\n{refined_query.purpose}\n--- END PURPOSE ---"
            if refined_query.purpose
            else ""
        )

        # Format the human message
        return HUMAN_MESSAGE.format(
            query=query_str,
            extra_requirements=extra_requirements_str,
            purpose=purpose_str,
            context="\n\n".join([str(context) for context in explored_context]),
        )

    def __call__(self, state: ContextRetrievalState):
        """
        Extract relevant code contexts from the codebase based on the refined query and existing context.
        The final contexts are with line numbers.
        """
        if not state["explored_context"]:
            self._logger.info("No explored_context available, skipping context extraction")
            return {"new_contexts": []}

        # Get human message
        human_message = self.format_human_message(state)

        # Log the human message for debugging
        self._logger.debug(human_message)

        # Summarize the context based on the last messages and system prompt
        response = self.model.invoke({"human_prompt": human_message})
        self._logger.debug(f"Model response: {response}")

        new_contexts = []
        context_list = response.context

        for context_ in context_list:
            if context_.start_line < 1 or context_.end_line < 1:
                self._logger.warning(
                    f"Skipping invalid context with start_line={context_.start_line}, end_line={context_.end_line}"
                )
                continue
            try:
                content = read_file_with_line_numbers(
                    relative_path=context_.relative_path,
                    root_path=str(self.root_path),
                    start_line=context_.start_line,
                    end_line=context_.end_line,
                )
            except FileOperationException as e:
                self._logger.error(e)
                continue

            # Skip empty content
            if not content:
                self._logger.warning(
                    f"Skipping context with empty content for {context_.relative_path} "
                    f"from line {context_.start_line} to {context_.end_line}"
                )
                continue
            context = Context(
                relative_path=context_.relative_path,
                start_line_number=context_.start_line,
                end_line_number=context_.end_line,
                content=content,
            )

            new_contexts.append(context)

        # return the new contexts after deduplication
        return {"new_contexts": deduplicate_contexts(new_contexts)}
