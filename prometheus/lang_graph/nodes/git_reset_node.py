from prometheus.git.git_repository import GitRepository
from prometheus.utils.logger_manager import get_thread_logger


class GitResetNode:
    def __init__(
        self,
        git_repo: GitRepository,
    ):
        self.git_repo = git_repo
        self._logger, file_handler = get_thread_logger(__name__)

    def __call__(self, _):
        self._logger.debug("Resetting the git repository")
        self.git_repo.reset_repository()
