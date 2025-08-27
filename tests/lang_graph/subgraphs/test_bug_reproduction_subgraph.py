from unittest.mock import Mock

import pytest

from prometheus.docker.base_container import BaseContainer
from prometheus.git.git_repository import GitRepository
from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.lang_graph.subgraphs.bug_reproduction_subgraph import BugReproductionSubgraph
from tests.test_utils.util import FakeListChatWithToolsModel


@pytest.fixture
def mock_container():
    return Mock(spec=BaseContainer)


@pytest.fixture
def mock_kg():
    kg = Mock(spec=KnowledgeGraph)
    kg.get_all_ast_node_types.return_value = ["FunctionDef", "ClassDef", "Module", "Import", "Call"]
    kg.root_node_id = 0
    return kg


@pytest.fixture
def mock_git_repo():
    git_repo = Mock(spec=GitRepository)
    git_repo.playground_path = "mock/playground/path"
    return git_repo


def test_bug_reproduction_subgraph_basic_initialization(mock_container, mock_kg, mock_git_repo):
    """Test that BugReproductionSubgraph initializes correctly with basic components."""
    # Initialize fake model with empty responses
    fake_advanced_model = FakeListChatWithToolsModel(responses=[])
    fake_base_model = FakeListChatWithToolsModel(responses=[])

    # Initialize the subgraph
    subgraph = BugReproductionSubgraph(
        fake_advanced_model,
        fake_base_model,
        mock_container,
        mock_kg,
        mock_git_repo,
        None,
    )

    # Verify the subgraph was created
    assert subgraph.subgraph is not None
