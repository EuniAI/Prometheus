import logging
import threading
from typing import Dict, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.errors import GraphRecursionError

from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.lang_graph.subgraphs.context_retrieval_subgraph import ContextRetrievalSubgraph
from prometheus.models.context import Context


class ContextRetrievalSubgraphNode:
    def __init__(
        self,
        base_model: BaseChatModel,
        advanced_model: BaseChatModel,
        kg: KnowledgeGraph,
        local_path: str,
        query_key_name: str,
        context_key_name: str,
        repository_id: int,
    ):
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")
        self.context_retrieval_subgraph = ContextRetrievalSubgraph(
            base_model=base_model,
            advanced_model=advanced_model,
            kg=kg,
            local_path=local_path,
            repository_id=repository_id,
        )
        self.query_key_name = query_key_name
        self.context_key_name = context_key_name

    def __call__(self, state: Dict) -> Dict[str, Sequence[Context]]:
        self._logger.info("Enter context retrieval subgraph")
        try:
            output_state = self.context_retrieval_subgraph.invoke(
                state[self.query_key_name], state["max_refined_query_loop"]
            )
        except GraphRecursionError as e:
            self._logger.debug("Graph recursion limit reached, returning empty context")
            raise e
        self._logger.info(f"Context retrieved: {output_state['context']}")
        return {self.context_key_name: output_state["context"]}
