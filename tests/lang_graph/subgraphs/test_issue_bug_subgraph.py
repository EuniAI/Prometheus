from unittest.mock import Mock

import pytest

from prometheus.docker.base_container import BaseContainer
from prometheus.git.git_repository import GitRepository
from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.lang_graph.subgraphs.issue_bug_subgraph import IssueBugSubgraph
from tests.test_utils.util import FakeListChatWithToolsModel


@pytest.fixture
def mock_container():
    return Mock(spec=BaseContainer)


@pytest.fixture
def mock_kg():
    kg = Mock(spec=KnowledgeGraph)
    # Configure the mock to return a list of AST node types
    kg.get_all_ast_node_types.return_value = ["FunctionDef", "ClassDef", "Module", "Import", "Call"]
    kg.root_node_id = 0
    return kg


@pytest.fixture
def mock_git_repo():
    git_repo = Mock(spec=GitRepository)
    git_repo.playground_path = "mock/playground/path"
    return git_repo


def test_issue_bug_subgraph_basic_initialization(mock_container, mock_kg, mock_git_repo):
    """Test that IssueBugSubgraph initializes correctly with basic components."""
    # Initialize fake model with empty responses
    fake_advanced_model = FakeListChatWithToolsModel(responses=[])
    fake_base_model = FakeListChatWithToolsModel(responses=[])

    # Initialize the subgraph with required parameters
    subgraph = IssueBugSubgraph(
        advanced_model=fake_advanced_model,
        base_model=fake_base_model,
        container=mock_container,
        kg=mock_kg,
        git_repo=mock_git_repo,
    )

    # Verify the subgraph was created
    assert subgraph.subgraph is not None


def test_issue_bug_subgraph_with_commands(mock_container, mock_kg, mock_git_repo):
    """Test that IssueBugSubgraph initializes correctly with build and test commands."""
    fake_advanced_model = FakeListChatWithToolsModel(responses=[])
    fake_base_model = FakeListChatWithToolsModel(responses=[])
    test_commands = ["make test"]

    subgraph = IssueBugSubgraph(
        advanced_model=fake_advanced_model,
        base_model=fake_base_model,
        container=mock_container,
        kg=mock_kg,
        git_repo=mock_git_repo,
        test_commands=test_commands,
    )

    assert subgraph.subgraph is not None
