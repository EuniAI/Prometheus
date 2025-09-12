from typing import Annotated, Mapping, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages

from prometheus.models.context import Context


class IssueQuestionState(TypedDict):
    issue_title: str
    issue_body: str
    issue_comments: Sequence[Mapping[str, str]]

    max_refined_query_loop: int

    question_query: str
    question_context: Sequence[Context]

    issue_question_analyzer_messages: Annotated[Sequence[BaseMessage], add_messages]

    question_response: str
