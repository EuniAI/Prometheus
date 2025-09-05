import pytest

from prometheus.app.services.neo4j_service import Neo4jService
from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.neo4j.knowledge_graph_handler import KnowledgeGraphHandler
from tests.test_utils import test_project_paths
from tests.test_utils.fixtures import (  # noqa: F401
    NEO4J_PASSWORD,
    NEO4J_USERNAME,
    empty_neo4j_container_fixture,
    neo4j_container_with_kg_fixture,
)


@pytest.fixture
async def mock_neo4j_service(neo4j_container_with_kg_fixture):  # noqa: F811
    """Fixture: provide a clean DatabaseService using the Postgres test container."""
    neo4j_container, kg = neo4j_container_with_kg_fixture
    service = Neo4jService(neo4j_container.get_connection_url(), NEO4J_USERNAME, NEO4J_PASSWORD)
    service.start()
    yield service
    await service.close()


@pytest.fixture
async def mock_empty_neo4j_service(empty_neo4j_container_fixture):  # noqa: F811
    """Fixture: provide a clean DatabaseService using the Postgres test container."""
    neo4j_container = empty_neo4j_container_fixture
    service = Neo4jService(neo4j_container.get_connection_url(), NEO4J_USERNAME, NEO4J_PASSWORD)
    service.start()
    yield service
    await service.close()


@pytest.mark.slow
async def test_num_ast_nodes(mock_neo4j_service):
    handler = KnowledgeGraphHandler(mock_neo4j_service.neo4j_driver, 100)

    async with mock_neo4j_service.neo4j_driver.session() as session:
        read_ast_nodes = await session.execute_read(handler._read_ast_nodes, root_node_id=0)
        assert len(read_ast_nodes) == 7


@pytest.mark.slow
async def test_num_file_nodes(mock_neo4j_service):
    handler = KnowledgeGraphHandler(mock_neo4j_service.neo4j_driver, 100)

    async with mock_neo4j_service.neo4j_driver.session() as session:
        read_file_nodes = await session.execute_read(handler._read_file_nodes, root_node_id=0)
        assert len(read_file_nodes) == 7


@pytest.mark.slow
async def test_num_text_nodes(mock_neo4j_service):
    handler = KnowledgeGraphHandler(mock_neo4j_service.neo4j_driver, 100)

    async with mock_neo4j_service.neo4j_driver.session() as session:
        read_text_nodes = await session.execute_read(handler._read_text_nodes, root_node_id=0)
        assert len(read_text_nodes) == 1


@pytest.mark.slow
async def test_num_parent_of_edges(mock_neo4j_service):
    handler = KnowledgeGraphHandler(mock_neo4j_service.neo4j_driver, 100)

    async with mock_neo4j_service.neo4j_driver.session() as session:
        read_parent_of_edges = await session.execute_read(
            handler._read_parent_of_edges, root_node_id=0
        )
        assert len(read_parent_of_edges) == 4


@pytest.mark.slow
async def test_num_has_file_edges(mock_neo4j_service):
    handler = KnowledgeGraphHandler(mock_neo4j_service.neo4j_driver, 100)

    async with mock_neo4j_service.neo4j_driver.session() as session:
        read_has_file_edges = await session.execute_read(
            handler._read_has_file_edges, root_node_id=0
        )
        assert len(read_has_file_edges) == 6


@pytest.mark.slow
async def test_num_has_ast_edges(mock_neo4j_service):
    handler = KnowledgeGraphHandler(mock_neo4j_service.neo4j_driver, 100)

    async with mock_neo4j_service.neo4j_driver.session() as session:
        read_has_ast_edges = await session.execute_read(handler._read_has_ast_edges, root_node_id=0)
        assert len(read_has_ast_edges) == 3


@pytest.mark.slow
async def test_num_has_text_edges(mock_neo4j_service):
    handler = KnowledgeGraphHandler(mock_neo4j_service.neo4j_driver, 100)

    async with mock_neo4j_service.neo4j_driver.session() as session:
        read_has_text_edges = await session.execute_read(
            handler._read_has_text_edges, root_node_id=0
        )
        assert len(read_has_text_edges) == 1


@pytest.mark.slow
async def test_num_next_chunk_edges(mock_neo4j_service):
    handler = KnowledgeGraphHandler(mock_neo4j_service.neo4j_driver, 100)

    async with mock_neo4j_service.neo4j_driver.session() as session:
        read_next_chunk_edges = await session.execute_read(
            handler._read_next_chunk_edges, root_node_id=0
        )
        assert len(read_next_chunk_edges) == 0


@pytest.mark.slow
async def test_clear_knowledge_graph(mock_empty_neo4j_service):
    kg = KnowledgeGraph(1, 1000, 100, 0)
    await kg.build_graph(test_project_paths.TEST_PROJECT_PATH)

    driver = mock_empty_neo4j_service.neo4j_driver
    handler = KnowledgeGraphHandler(driver, 100)
    await handler.write_knowledge_graph(kg)

    await handler.clear_knowledge_graph(0)

    # Verify that the graph is cleared
    async with driver.session() as session:
        result = await session.run("MATCH (n) RETURN COUNT(n) AS node_count")
        record = await result.single()
        node_count = record["node_count"]
        assert node_count == 0
