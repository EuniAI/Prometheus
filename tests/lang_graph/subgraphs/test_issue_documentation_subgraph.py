from unittest.mock import Mock

import pytest

from prometheus.git.git_repository import GitRepository
from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.lang_graph.subgraphs.issue_documentation_subgraph import (
    IssueDocumentationSubgraph,
)
from tests.test_utils.util import FakeListChatWithToolsModel


@pytest.fixture
def mock_kg():
    kg = Mock(spec=KnowledgeGraph)
    # Configure the mock to return a list of AST node types
    kg.get_all_ast_node_types.return_value = [
        "FunctionDef",
        "ClassDef",
        "Module",
        "Import",
        "Call",
    ]
    kg.root_node_id = 0
    return kg


@pytest.fixture
def mock_git_repo():
    git_repo = Mock(spec=GitRepository)
    git_repo.playground_path = "mock/playground/path"
    return git_repo


def test_issue_documentation_subgraph_basic_initialization(mock_kg, mock_git_repo):
    """Test that IssueDocumentationSubgraph initializes correctly with basic components."""
    # Initialize fake model with empty responses
    fake_advanced_model = FakeListChatWithToolsModel(responses=[])
    fake_base_model = FakeListChatWithToolsModel(responses=[])

    # Initialize the subgraph with required parameters
    subgraph = IssueDocumentationSubgraph(
        advanced_model=fake_advanced_model,
        base_model=fake_base_model,
        kg=mock_kg,
        git_repo=mock_git_repo,
        repository_id=1,
    )

    # Verify the subgraph was created
    assert subgraph.subgraph is not None
