import threading

from langchain_core.language_models.chat_models import BaseChatModel

from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.lang_graph.graphs.issue_state import IssueState
from prometheus.lang_graph.subgraphs.issue_classification_subgraph import (
    IssueClassificationSubgraph,
)
from prometheus.utils.logger_manager import get_logger


class IssueClassificationSubgraphNode:
    def __init__(
        self,
        model: BaseChatModel,
        kg: KnowledgeGraph,
        local_path: str,
    ):
        self._logger = get_logger(f"thread-{threading.get_ident()}.{__name__}")
        self.issue_classification_subgraph = IssueClassificationSubgraph(
            model=model,
            kg=kg,
            local_path=local_path,
        )

    def __call__(self, state: IssueState):
        self._logger.info("Enter IssueClassificationSubgraphNode")
        issue_type = self.issue_classification_subgraph.invoke(
            state["issue_title"], state["issue_body"], state["issue_comments"]
        )
        self._logger.info(f"issue_type: {issue_type}")
        return {"issue_type": issue_type}
