"""The neo4j handler for writing the knowledge graph to neo4j."""

from typing import Mapping, Sequence

from neo4j import AsyncGraphDatabase, AsyncManagedTransaction

from prometheus.graph.graph_types import (
    KnowledgeGraphNode,
    Neo4jASTNode,
    Neo4jFileNode,
    Neo4jHasASTEdge,
    Neo4jHasFileEdge,
    Neo4jHasTextEdge,
    Neo4jNextChunkEdge,
    Neo4jTextNode,
)
from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.utils.logger_manager import get_thread_logger


class KnowledgeGraphHandler:
    """The handler to writing the Knowledge graph to neo4j."""

    def __init__(self, driver: AsyncGraphDatabase.driver, batch_size: int):
        """
        Args:
          driver: The neo4j driver.
          batch_size: The maximum number of nodes/edges written to neo4j each time.
        """
        self.driver = driver
        self.batch_size = batch_size
        # initialize the database and logger
        self._logger, file_handler = get_thread_logger(__name__)

    async def init_database(self):
        """Initialization of the neo4j database."""

        # Create constraints for node_id attributes.
        # It also means that node_id will be indexed.
        queries = [
            "CREATE CONSTRAINT unique_file_node_id IF NOT EXISTS "
            "FOR (n:FileNode) REQUIRE n.node_id IS UNIQUE",
            "CREATE CONSTRAINT unique_ast_node_id IF NOT EXISTS "
            "FOR (n:ASTNode) REQUIRE n.node_id IS UNIQUE",
            "CREATE CONSTRAINT unique_text_node_id IF NOT EXISTS "
            "FOR (n:TextNode) REQUIRE n.node_id IS UNIQUE",
        ]
        async with self.driver.session() as session:
            for query in queries:
                await session.run(query)

    async def _write_file_nodes(
        self, tx: AsyncManagedTransaction, file_nodes: Sequence[Neo4jFileNode]
    ):
        """Write Neo4jFileNode to neo4j."""
        self._logger.debug(f"Writing {len(file_nodes)} FileNode to neo4j")
        query = """
      UNWIND $file_nodes AS file_node
      CREATE (a:FileNode {node_id: file_node.node_id, basename: file_node.basename, relative_path: file_node.relative_path})
    """
        for i in range(0, len(file_nodes), self.batch_size):
            file_nodes_batch = file_nodes[i : i + self.batch_size]
            await tx.run(query, file_nodes=file_nodes_batch)

    async def _write_ast_nodes(
        self, tx: AsyncManagedTransaction, ast_nodes: Sequence[Neo4jASTNode]
    ):
        """Write Neo4jASTNode to neo4j."""
        self._logger.debug(f"Writing {len(ast_nodes)} ASTNode to neo4j")
        query = """
      UNWIND $ast_nodes AS ast_node
      CREATE (a:ASTNode {node_id: ast_node.node_id, start_line: ast_node.start_line, end_line: ast_node.end_line, type: ast_node.type, text: ast_node.text})
    """
        for i in range(0, len(ast_nodes), self.batch_size):
            ast_nodes_batch = ast_nodes[i : i + self.batch_size]
            await tx.run(query, ast_nodes=ast_nodes_batch)

    async def _write_text_nodes(
        self, tx: AsyncManagedTransaction, text_nodes: Sequence[Neo4jTextNode]
    ):
        """Write Neo4jTextNode to neo4j."""
        self._logger.debug(f"Writing {len(text_nodes)} TextNode to neo4j")
        query = """
      UNWIND $text_nodes AS text_node
      CREATE (a:TextNode {node_id: text_node.node_id, text: text_node.text, start_line: text_node.start_line, end_line: text_node.end_line})
    """
        for i in range(0, len(text_nodes), self.batch_size):
            text_nodes_batch = text_nodes[i : i + self.batch_size]
            await tx.run(query, text_nodes=text_nodes_batch)

    async def _write_has_file_edges(
        self, tx: AsyncManagedTransaction, has_file_edges: Sequence[Neo4jHasFileEdge]
    ):
        """Write Neo4jHasFileEdge to neo4j."""
        self._logger.debug(f"Writing {len(has_file_edges)} HasFileEdge to neo4j")
        query = """
      UNWIND $edges AS edge
      MATCH (source:FileNode), (target:FileNode)
      WHERE source.node_id = edge.source.node_id AND target.node_id = edge.target.node_id
      CREATE (source) -[:HAS_FILE]-> (target)
    """
        for i in range(0, len(has_file_edges), self.batch_size):
            has_file_edges_batch = has_file_edges[i : i + self.batch_size]
            await tx.run(query, edges=has_file_edges_batch)

    async def _write_has_ast_edges(
        self, tx: AsyncManagedTransaction, has_ast_edges: Sequence[Neo4jHasASTEdge]
    ):
        """Write Neo4jHasASTEdge to neo4j."""
        self._logger.debug(f"Writing {len(has_ast_edges)} HasASTEdge to neo4j")
        query = """
      UNWIND $edges AS edge
      MATCH (source:FileNode), (target:ASTNode)
      WHERE source.node_id = edge.source.node_id AND target.node_id = edge.target.node_id
      CREATE (source) -[:HAS_AST]-> (target)
    """
        for i in range(0, len(has_ast_edges), self.batch_size):
            has_ast_edges_batch = has_ast_edges[i : i + self.batch_size]
            await tx.run(query, edges=has_ast_edges_batch)

    async def _write_has_text_edges(
        self, tx: AsyncManagedTransaction, has_text_edges: Sequence[Neo4jHasTextEdge]
    ):
        """Write Neo4jHasTextEdge to neo4j."""
        self._logger.debug(f"Writing {len(has_text_edges)} HasTextEdges to neo4j")
        query = """
      UNWIND $edges AS edge
      MATCH (source:FileNode), (target:TextNode)
      WHERE source.node_id = edge.source.node_id AND target.node_id = edge.target.node_id
      CREATE (source) -[:HAS_TEXT]-> (target)
    """
        for i in range(0, len(has_text_edges), self.batch_size):
            has_text_edges_batch = has_text_edges[i : i + self.batch_size]
            await tx.run(query, edges=has_text_edges_batch)

    async def write_parent_of_edges(self, parent_of_edges):
        self._logger.debug(f"Writing {len(parent_of_edges)} ParentOfEdge to neo4j")

        query = """
            UNWIND $edges AS edge
            MATCH (source:ASTNode {node_id: edge.source.node_id})
            MATCH (target:ASTNode {node_id: edge.target.node_id})
            CREATE (source)-[:PARENT_OF]->(target)
        """

        for i in range(0, len(parent_of_edges), self.batch_size):
            parent_of_edges_batch = parent_of_edges[i : i + self.batch_size]
            edge_dicts = [
                {
                    "source": {"node_id": e.source.node_id},
                    "target": {"node_id": e.target.node_id},
                }
                for e in parent_of_edges_batch
            ]
            async with self.driver.session() as session:
                await session.write_transaction(lambda tx: tx.run(query, edges=edge_dicts))

    async def _write_next_chunk_edges(
        self, tx: AsyncManagedTransaction, next_chunk_edges: Sequence[Neo4jNextChunkEdge]
    ):
        """Write Neo4jNextChunkEdge to neo4j."""
        self._logger.debug(f"Writing {len(next_chunk_edges)} NextChunkEdge to neo4j")
        query = """
      UNWIND $edges AS edge
      MATCH (source:TextNode), (target:TextNode)
      WHERE source.node_id = edge.source.node_id AND target.node_id = edge.target.node_id
      CREATE (source) -[:NEXT_CHUNK]-> (target)
    """
        for i in range(0, len(next_chunk_edges), self.batch_size):
            next_chunk_edges_batch = next_chunk_edges[i : i + self.batch_size]
            await tx.run(query, edges=next_chunk_edges_batch)

    async def write_knowledge_graph(self, kg: KnowledgeGraph):
        """Write the knowledge graph to neo4j.

        Args:
          kg: The knowledge graph to write to neo4j.
        """
        self._logger.info("Writing knowledge graph to neo4j")
        async with self.driver.session() as session:
            await session.execute_write(self._write_file_nodes, kg.get_neo4j_file_nodes())
            await session.execute_write(self._write_ast_nodes, kg.get_neo4j_ast_nodes())
            await session.execute_write(self._write_text_nodes, kg.get_neo4j_text_nodes())

            await session.execute_write(self._write_has_ast_edges, kg.get_neo4j_has_ast_edges())
            await session.execute_write(self._write_has_file_edges, kg.get_neo4j_has_file_edges())
            await session.execute_write(self._write_has_text_edges, kg.get_neo4j_has_text_edges())
            await session.execute_write(
                self._write_next_chunk_edges, kg.get_neo4j_next_chunk_edges()
            )
        await self.write_parent_of_edges(kg.get_parent_of_edges())

    async def _read_file_nodes(
        self, tx: AsyncManagedTransaction, root_node_id: int
    ) -> Sequence[KnowledgeGraphNode]:
        """
        Read all FileNode nodes that are reachable from the specified root_node_id (including the root node itself).

        Args:
            tx (AsyncManagedTransaction): An active Neo4j transaction.
            root_node_id (int): The node id of the root node.

        Returns:
            Sequence[KnowledgeGraphNode]: List of FileNode KnowledgeGraphNode objects.
        """
        query = """
        MATCH (root:FileNode {node_id: $root_node_id})
        RETURN root.node_id AS node_id, root.basename AS basename, root.relative_path AS relative_path
        UNION
        MATCH (root:FileNode {node_id: $root_node_id})-[:HAS_FILE*]->(n:FileNode)
        RETURN n.node_id AS node_id, n.basename AS basename, n.relative_path AS relative_path
        """
        result = await tx.run(query, root_node_id=root_node_id)
        records = await result.data()
        return [KnowledgeGraphNode.from_neo4j_file_node(record) for record in records]

    async def _read_ast_nodes(
        self, tx: AsyncManagedTransaction, root_node_id: int
    ) -> Sequence[KnowledgeGraphNode]:
        """
        Read all ASTNode nodes related to the file tree rooted at root_node_id:
          - Traverse from the root FileNode via HAS_FILE* to get all reachable FileNodes.
          - For each FileNode, get its AST root node via HAS_AST, and all its AST descendants via PARENT_OF*.

        Args:
            tx (AsyncManagedTransaction): An active Neo4j transaction.
            root_node_id (int): The node id of the root FileNode.

        Returns:
            Sequence[KnowledgeGraphNode]: List of ASTNode KnowledgeGraphNode objects.
        """
        query = """
        MATCH (root {node_id: $root_node_id})
        OPTIONAL MATCH (root)-[*]->(n:ASTNode)
        RETURN DISTINCT n.node_id AS node_id, n.start_line AS start_line, n.end_line AS end_line, n.type AS type, n.text AS text
        """
        result = await tx.run(query, root_node_id=root_node_id)
        records = await result.data()
        return [KnowledgeGraphNode.from_neo4j_ast_node(record) for record in records]

    async def _read_text_nodes(
        self, tx: AsyncManagedTransaction, root_node_id: int
    ) -> Sequence[KnowledgeGraphNode]:
        """
        Read all TextNode nodes that are reachable from the specified root_node_id (regardless of edge type).

        Args:
            tx (AsyncManagedTransaction): An active Neo4j transaction.
            root_node_id (int): The node id of the root node.

        Returns:
            Sequence[KnowledgeGraphNode]: List of TextNode KnowledgeGraphNode objects.
        """
        query = """
        MATCH (root {node_id: $root_node_id})
        OPTIONAL MATCH (root)-[*]->(n:TextNode)
        RETURN DISTINCT n.node_id AS node_id, n.text AS text, n.start_line AS start_line, n.end_line AS end_line
        """
        result = await tx.run(query, root_node_id=root_node_id)
        records = await result.data()
        return [KnowledgeGraphNode.from_neo4j_text_node(record) for record in records]

    async def _read_parent_of_edges(
        self, tx: AsyncManagedTransaction, root_node_id: int
    ) -> Sequence[Mapping[str, int]]:
        """
        Read all PARENT_OF edges where both source and target ASTNode are reachable from the subtree rooted at root_node_id.

        Args:
            tx (AsyncManagedTransaction): An active Neo4j transaction.
            root_node_id (int): The node id of the root FileNode.

        Returns:
            Sequence[Mapping[str, int]]: List of dicts with source_id and target_id for each PARENT_OF edge.
        """
        query = """
        // Find all reachable ASTNodes (from the file tree)
        MATCH (root:FileNode {node_id: $root_node_id})
        OPTIONAL MATCH (root)-[*]->(ast:ASTNode)
        WITH collect(ast) AS all_ast_nodes
        UNWIND all_ast_nodes AS node1
        WITH node1, all_ast_nodes WHERE node1 IS NOT NULL
        // Find PARENT_OF edges only between those ASTNodes
        MATCH (node1)-[:PARENT_OF]->(node2:ASTNode)
        WHERE node2 IN all_ast_nodes
        RETURN node1.node_id AS source_id, node2.node_id AS target_id
        """
        result = await tx.run(query, root_node_id=root_node_id)
        records = await result.data()
        return records

    async def _read_has_file_edges(
        self, tx: AsyncManagedTransaction, root_node_id: int
    ) -> Sequence[Mapping[str, int]]:
        """
        Read all HAS_FILE edges that are reachable from the specified root_node_id (i.e., only those
        between FileNodes in the subtree of root_node_id, including root itself).

        Args:
            tx (AsyncManagedTransaction): An active Neo4j transaction.
            root_node_id (int): The node id of the root FileNode.

        Returns:
            Sequence[Mapping[str, int]]: List of dicts with source_id and target_id for each HAS_FILE edge.
        """
        query = """
            MATCH p = (root:FileNode {node_id: $root_node_id})-[:HAS_FILE*0..]->(n:FileNode)
            WITH collect(DISTINCT n) AS nodes_in_subtree
            UNWIND nodes_in_subtree AS src
            MATCH (src)-[:HAS_FILE]->(dst:FileNode)
            WHERE dst IN nodes_in_subtree
            RETURN DISTINCT src.node_id AS source_id, dst.node_id AS target_id
            """
        result = await tx.run(query, root_node_id=root_node_id)
        records = await result.data()
        return records

    async def _read_has_ast_edges(
        self, tx: AsyncManagedTransaction, root_node_id: int
    ) -> Sequence[Mapping[str, int]]:
        """
        Read all HAS_AST edges where the source FileNode is in the subtree rooted at root_node_id.

        Args:
            tx (AsyncManagedTransaction): An active Neo4j transaction.
            root_node_id (int): The node id of the root FileNode.

        Returns:
            Sequence[Mapping[str, int]]: List of dicts with source_id and target_id for each HAS_AST edge.
        """
        query = """
        // Find all reachable FileNodes (including root)
        MATCH (root:FileNode {node_id: $root_node_id})
        OPTIONAL MATCH (root)-[:HAS_FILE*]->(subfile:FileNode)
        WITH collect(root) + collect(subfile) AS all_file_nodes
        UNWIND all_file_nodes AS file_node
        WITH file_node WHERE file_node IS NOT NULL
        // Find HAS_AST edges from these FileNodes
        MATCH (file_node)-[:HAS_AST]->(ast:ASTNode)
        RETURN file_node.node_id AS source_id, ast.node_id AS target_id
        """
        result = await tx.run(query, root_node_id=root_node_id)
        records = await result.data()
        return records

    async def _read_has_text_edges(
        self, tx: AsyncManagedTransaction, root_node_id: int
    ) -> Sequence[Mapping[str, int]]:
        """
        Read all HAS_TEXT edges where the source FileNode is in the subtree rooted at root_node_id.

        Args:
            tx (AsyncManagedTransaction): An active Neo4j transaction.
            root_node_id (int): The node id of the root FileNode.

        Returns:
            Sequence[Mapping[str, int]]: List of dicts with source_id and target_id for each HAS_TEXT edge.
        """
        query = """
        // Find all reachable FileNodes (including root)
        MATCH (root:FileNode {node_id: $root_node_id})
        OPTIONAL MATCH (root)-[:HAS_FILE*]->(subfile:FileNode)
        WITH collect(root) + collect(subfile) AS all_file_nodes
        UNWIND all_file_nodes AS file_node
        WITH file_node WHERE file_node IS NOT NULL
        // Find HAS_TEXT edges from these FileNodes
        MATCH (file_node)-[:HAS_TEXT]->(text:TextNode)
        RETURN file_node.node_id AS source_id, text.node_id AS target_id
        """
        result = await tx.run(query, root_node_id=root_node_id)
        records = await result.data()
        return records

    async def _read_next_chunk_edges(
        self, tx: AsyncManagedTransaction, root_node_id: int
    ) -> Sequence[Mapping[str, int]]:
        """
        Read all NEXT_CHUNK edges between TextNodes that are reachable from the subtree rooted at root_node_id.

        Args:
            tx (AsyncManagedTransaction): An active Neo4j transaction.
            root_node_id (int): The node id of the root FileNode.

        Returns:
            Sequence[Mapping[str, int]]: List of dicts with source_id and target_id for each NEXT_CHUNK edge.
        """
        query = """
        // Find all reachable TextNodes (from the file tree)
        MATCH (root:FileNode {node_id: $root_node_id})
        OPTIONAL MATCH (root)-[*]->(text_node:TextNode)
        WITH collect(text_node) AS all_text_nodes
        UNWIND all_text_nodes AS node1
        WITH node1, all_text_nodes WHERE node1 IS NOT NULL
        // Find NEXT_CHUNK edges only between those TextNodes
        MATCH (node1)-[:NEXT_CHUNK]->(node2:TextNode)
        WHERE node2 IN all_text_nodes
        RETURN node1.node_id AS source_id, node2.node_id AS target_id
        """
        result = await tx.run(query, root_node_id=root_node_id)
        records = await result.data()
        return records

    async def read_knowledge_graph(
        self,
        root_node_id: int,
        max_ast_depth: int,
        chunk_size: int,
        chunk_overlap: int,
    ) -> KnowledgeGraph:
        """Read KnowledgeGraph from neo4j."""
        self._logger.info("Reading knowledge graph from neo4j")
        async with self.driver.session() as session:
            return KnowledgeGraph.from_neo4j(
                root_node_id,
                max_ast_depth,
                chunk_size,
                chunk_overlap,
                await session.execute_read(self._read_file_nodes, root_node_id=root_node_id),
                await session.execute_read(self._read_ast_nodes, root_node_id=root_node_id),
                await session.execute_read(self._read_text_nodes, root_node_id=root_node_id),
                await session.execute_read(self._read_parent_of_edges, root_node_id=root_node_id),
                await session.execute_read(self._read_has_file_edges, root_node_id=root_node_id),
                await session.execute_read(self._read_has_ast_edges, root_node_id=root_node_id),
                await session.execute_read(self._read_has_text_edges, root_node_id=root_node_id),
                await session.execute_read(self._read_next_chunk_edges, root_node_id=root_node_id),
            )

    async def get_new_knowledge_graph_root_node_id(self) -> int:
        """
        Estimate the next available node id in the Neo4j database.

        Returns:
            int: The next available node id (max id + 1), or 0 if no nodes exist.
        """
        query = """
        MATCH (n)
        WHERE n.node_id IS NOT NULL
        RETURN coalesce(max(n.node_id), -1) AS max_node_id"""
        async with self.driver.session() as session:
            result = await session.run(query)
            record = await result.single()
            max_node_id = record["max_node_id"]
            return int(max_node_id) + 1

    async def clear_knowledge_graph(self, root_node_id: int):
        """
        Delete the subgraph rooted at root_node_id, including all descendant nodes and their relationships.

        Args:
            root_node_id (int): The node id of the root node.
        """
        query = """
        MATCH (root {node_id: $root_node_id})
        OPTIONAL MATCH (root)-[*]->(descendant)
        DETACH DELETE root, descendant
        """
        async with self.driver.session() as session:
            await session.run(query, root_node_id=root_node_id)
