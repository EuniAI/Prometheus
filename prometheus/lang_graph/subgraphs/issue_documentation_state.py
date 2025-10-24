from typing import Annotated, Mapping, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages

from prometheus.models.context import Context


class IssueDocumentationState(TypedDict):
    issue_title: str
    issue_body: str
    issue_comments: Sequence[Mapping[str, str]]

    max_refined_query_loop: int

    documentation_query: str
    documentation_context: Sequence[Context]

    issue_documentation_analyzer_messages: Annotated[Sequence[BaseMessage], add_messages]
    edit_messages: Annotated[Sequence[BaseMessage], add_messages]

    edit_patch: str
    issue_response: str
