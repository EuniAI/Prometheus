from prometheus.lang_graph.subgraphs.issue_question_state import IssueQuestionState
from prometheus.utils.lang_graph_util import get_last_message_content
from prometheus.utils.logger_manager import get_thread_logger


class IssueQuestionResponderNode:
    def __init__(self):
        self._logger, file_handler = get_thread_logger(__name__)

    def __call__(self, state: IssueQuestionState):
        response = (get_last_message_content(state["issue_question_analyzer_messages"]),)
        self._logger.debug(response)
        return {"question_response": response[0]}
