import logging
import threading

from langchain_core.language_models.chat_models import BaseChatModel

from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.lang_graph.graphs.issue_state import IssueState
from prometheus.lang_graph.subgraphs.issue_classification_subgraph import (
    IssueClassificationSubgraph,
)


class IssueClassificationSubgraphNode:
    def __init__(
        self,
        advanced_model: BaseChatModel,
        model: BaseChatModel,
        kg: KnowledgeGraph,
        local_path: str,
        repository_id: int,
    ):
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")
        self.issue_classification_subgraph = IssueClassificationSubgraph(
            advanced_model=advanced_model,
            model=model,
            kg=kg,
            local_path=local_path,
            repository_id=repository_id,
        )

    def __call__(self, state: IssueState):
        self._logger.info("Enter IssueClassificationSubgraphNode")
        issue_type = self.issue_classification_subgraph.invoke(
            state["issue_title"], state["issue_body"], state["issue_comments"]
        )
        self._logger.info(f"issue_type: {issue_type}")
        return {"issue_type": issue_type}
