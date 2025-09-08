import pytest

from prometheus.app.services.neo4j_service import Neo4jService
from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.neo4j.knowledge_graph_handler import KnowledgeGraphHandler
from tests.test_utils import test_project_paths
from tests.test_utils.fixtures import (
    NEO4J_PASSWORD,
    NEO4J_USERNAME,
    neo4j_container_with_kg_fixture,  # noqa: F401
)


@pytest.fixture
async def mock_neo4j_service(neo4j_container_with_kg_fixture):  # noqa: F811
    """Fixture: provide a clean DatabaseService using the Postgres test container."""
    neo4j_container, kg = neo4j_container_with_kg_fixture
    service = Neo4jService(neo4j_container.get_connection_url(), NEO4J_USERNAME, NEO4J_PASSWORD)
    service.start()
    yield service, kg
    await service.close()


async def test_build_graph():
    knowledge_graph = KnowledgeGraph(1, 1000, 100, 0)
    await knowledge_graph.build_graph(test_project_paths.TEST_PROJECT_PATH)

    assert knowledge_graph._next_node_id == 15
    # 7 FileNode
    # 84 ASTnode
    # 2 TextNode
    assert len(knowledge_graph._knowledge_graph_nodes) == 15
    assert len(knowledge_graph._knowledge_graph_edges) == 14

    assert len(knowledge_graph.get_file_nodes()) == 7
    assert len(knowledge_graph.get_ast_nodes()) == 7
    assert len(knowledge_graph.get_text_nodes()) == 1
    assert len(knowledge_graph.get_parent_of_edges()) == 4
    assert len(knowledge_graph.get_has_file_edges()) == 6
    assert len(knowledge_graph.get_has_ast_edges()) == 3
    assert len(knowledge_graph.get_has_text_edges()) == 1
    assert len(knowledge_graph.get_next_chunk_edges()) == 0


async def test_get_file_tree():
    knowledge_graph = KnowledgeGraph(1000, 1000, 100, 0)
    await knowledge_graph.build_graph(test_project_paths.TEST_PROJECT_PATH)
    file_tree = knowledge_graph.get_file_tree()
    expected_file_tree = """\
test_project
├── bar
|   ├── test.java
|   └── test.py
├── foo
|   └── test.md
└── test.c"""
    assert file_tree == expected_file_tree


async def test_get_file_tree_depth_one():
    knowledge_graph = KnowledgeGraph(1000, 1000, 100, 0)
    await knowledge_graph.build_graph(test_project_paths.TEST_PROJECT_PATH)
    file_tree = knowledge_graph.get_file_tree(max_depth=1)
    expected_file_tree = """\
test_project
├── bar
├── foo
└── test.c"""
    assert file_tree == expected_file_tree


async def test_get_file_tree_depth_two_max_seven_lines():
    knowledge_graph = KnowledgeGraph(1000, 1000, 100, 0)
    await knowledge_graph.build_graph(test_project_paths.TEST_PROJECT_PATH)
    file_tree = knowledge_graph.get_file_tree(max_depth=2, max_lines=6)
    expected_file_tree = """\
test_project
├── bar
|   ├── test.java
|   └── test.py
├── foo
|   └── test.md"""
    assert file_tree == expected_file_tree


@pytest.mark.slow
async def test_from_neo4j(mock_neo4j_service):
    service, kg = mock_neo4j_service
    handler = KnowledgeGraphHandler(service.neo4j_driver, 100)
    read_kg = await handler.read_knowledge_graph(0, 1000, 100, 10)

    assert read_kg == kg
