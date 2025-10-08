from unittest.mock import Mock, create_autospec

import pytest

from prometheus.app.services.issue_service import IssueService
from prometheus.app.services.llm_service import LLMService
from prometheus.app.services.repository_service import RepositoryService
from prometheus.git.git_repository import GitRepository
from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.lang_graph.graphs.issue_state import IssueType


@pytest.fixture
def mock_llm_service():
    service = create_autospec(LLMService, instance=True)
    service.advanced_model = "gpt-4"
    service.base_model = "gpt-3.5-turbo"
    return service


@pytest.fixture
def mock_repository_service():
    service = create_autospec(RepositoryService, instance=True)
    return service


@pytest.fixture
def issue_service(mock_llm_service, mock_repository_service):
    return IssueService(
        llm_service=mock_llm_service,
        working_directory="/tmp/working_dir/",
        logging_level="DEBUG",
    )


async def test_answer_issue_with_general_container(issue_service, monkeypatch):
    # Setup
    mock_issue_graph = Mock()
    mock_issue_graph_class = Mock(return_value=mock_issue_graph)
    monkeypatch.setattr("prometheus.app.services.issue_service.IssueGraph", mock_issue_graph_class)

    mock_container = Mock()
    mock_general_container_class = Mock(return_value=mock_container)
    monkeypatch.setattr(
        "prometheus.app.services.issue_service.GeneralContainer", mock_general_container_class
    )

    repository = Mock(spec=GitRepository)
    repository.get_working_directory.return_value = "mock/working/directory"

    knowledge_graph = Mock(spec=KnowledgeGraph)

    # Mock output state for a bug type
    mock_output_state = {
        "issue_type": IssueType.BUG,
        "edit_patch": "test_patch",
        "passed_reproducing_test": True,
        "passed_regression_test": True,
        "passed_existing_test": True,
        "issue_response": "test_response",
    }
    mock_issue_graph.invoke.return_value = mock_output_state

    # Exercise
    result = issue_service.answer_issue(
        repository=repository,
        knowledge_graph=knowledge_graph,
        repository_id=1,
        issue_title="Test Issue",
        issue_body="Test Body",
        issue_comments=[],
        issue_type=IssueType.BUG,
        run_build=True,
        run_regression_test=True,
        run_existing_test=True,
        run_reproduce_test=True,
        number_of_candidate_patch=1,
        build_commands=None,
        test_commands=None,
    )

    # Verify
    mock_general_container_class.assert_called_once_with(
        project_path=repository.get_working_directory(), build_commands=None, test_commands=None
    )

    mock_issue_graph_class.assert_called_once_with(
        advanced_model=issue_service.llm_service.advanced_model,
        base_model=issue_service.llm_service.base_model,
        kg=knowledge_graph,
        git_repo=repository,
        container=mock_container,
        repository_id=1,
        test_commands=None,
    )
    assert result == ("test_patch", True, True, True, "test_response", IssueType.BUG)


async def test_answer_issue_with_user_defined_container(issue_service, monkeypatch):
    # Setup
    mock_issue_graph = Mock()
    mock_issue_graph_class = Mock(return_value=mock_issue_graph)
    monkeypatch.setattr("prometheus.app.services.issue_service.IssueGraph", mock_issue_graph_class)

    mock_container = Mock()
    mock_user_container_class = Mock(return_value=mock_container)
    monkeypatch.setattr(
        "prometheus.app.services.issue_service.UserDefinedContainer", mock_user_container_class
    )

    repository = Mock(spec=GitRepository)
    repository.get_working_directory.return_value = "mock/working/directory"

    knowledge_graph = Mock(spec=KnowledgeGraph)

    # Mock output state for a question type
    mock_output_state = {
        "issue_type": IssueType.QUESTION,
        "edit_patch": None,
        "passed_reproducing_test": False,
        "passed_regression_test": False,
        "passed_existing_test": False,
        "issue_response": "test_response",
    }
    mock_issue_graph.invoke.return_value = mock_output_state

    # Exercise
    result = issue_service.answer_issue(
        repository=repository,
        knowledge_graph=knowledge_graph,
        repository_id=1,
        issue_title="Test Issue",
        issue_body="Test Body",
        issue_comments=[],
        issue_type=IssueType.QUESTION,
        run_build=True,
        run_regression_test=True,
        run_existing_test=True,
        run_reproduce_test=True,
        number_of_candidate_patch=1,
        dockerfile_content="FROM python:3.8",
        image_name="test-image",
        workdir="/app",
        build_commands=["pip install -r requirements.txt"],
        test_commands=["pytest"],
    )

    # Verify
    mock_user_container_class.assert_called_once_with(
        project_path=repository.get_working_directory(),
        workdir="/app",
        build_commands=["pip install -r requirements.txt"],
        test_commands=["pytest"],
        dockerfile_content="FROM python:3.8",
        image_name="test-image",
    )
    assert result == (None, False, False, False, "test_response", IssueType.QUESTION)
