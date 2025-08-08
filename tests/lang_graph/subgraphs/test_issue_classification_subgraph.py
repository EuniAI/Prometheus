from unittest.mock import Mock

import neo4j
import pytest

from prometheus.git.git_repository import GitRepository
from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.lang_graph.subgraphs.issue_classification_subgraph import (
    IssueClassificationSubgraph,
)
from tests.test_utils.util import FakeListChatWithToolsModel


@pytest.fixture
def mock_kg():
    kg = Mock(spec=KnowledgeGraph)
    # Configure the mock to return a list of AST node types
    kg.get_all_ast_node_types.return_value = ["FunctionDef", "ClassDef", "Module", "Import", "Call"]
    return kg


@pytest.fixture
def mock_git_repo():
    git_repo = Mock(spec=GitRepository)
    git_repo.playground_path = "mock/playground/path"
    return git_repo


@pytest.fixture
def mock_neo4j_driver():
    return Mock(spec=neo4j.Driver)


def test_issue_classification_subgraph_basic_initialization(
    mock_kg, mock_git_repo, mock_neo4j_driver
):
    """Test that IssueClassificationSubgraph initializes correctly with basic components."""
    # Initialize fake model with empty responses
    fake_model = FakeListChatWithToolsModel(responses=[])

    # Initialize the subgraph with required parameters
    subgraph = IssueClassificationSubgraph(
        model=fake_model,
        kg=mock_kg,
        local_path=mock_git_repo.playground_path,
        neo4j_driver=mock_neo4j_driver,
        max_token_per_neo4j_result=1000,
    )

    # Verify the subgraph was created
    assert subgraph.subgraph is not None
