from operator import add
from typing import Annotated, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from prometheus.models.context import Context
from prometheus.models.query import Query


class ContextRetrievalState(TypedDict):
    query: str
    max_refined_query_loop: int

    context_provider_messages: Annotated[Sequence[BaseMessage], add_messages]
    refined_query: Query
    previous_refined_queries: Annotated[Sequence[Query], add]

    context: Sequence[Context]  # Final contexts to return

    explored_context: Sequence[
        Context
    ]  # contexts explored during the process (both from memory and KG)

    new_contexts: Sequence[Context]  # Newly extracted contexts (to be added to memory)
