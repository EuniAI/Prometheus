from prometheus.graph.file_graph_builder import FileGraphBuilder
from prometheus.graph.graph_types import (
    ASTNode,
    KnowledgeGraphEdgeType,
    KnowledgeGraphNode,
    TextNode,
)
from tests.test_utils import test_project_paths


def test_supports_file():
    file_graph_builder = FileGraphBuilder(0, 0, 0)

    assert file_graph_builder.supports_file(test_project_paths.C_FILE)
    assert file_graph_builder.supports_file(test_project_paths.JAVA_FILE)
    assert file_graph_builder.supports_file(test_project_paths.MD_FILE)
    assert file_graph_builder.supports_file(test_project_paths.PYTHON_FILE)

    assert file_graph_builder.supports_file(test_project_paths.DUMMY_FILE) is False


def test_build_python_file_graph():
    file_graph_builder = FileGraphBuilder(1000, 1000, 100)

    parent_kg_node = KnowledgeGraphNode(0, None)
    next_node_id, kg_nodes, kg_edges = file_graph_builder.build_file_graph(
        parent_kg_node, test_project_paths.PYTHON_FILE, 0
    )

    assert next_node_id == 11
    assert len(kg_nodes) == 11
    assert len(kg_edges) == 11

    # Test if some of the nodes exists
    argument_list_ast_node = ASTNode(
        type="argument_list", start_line=1, end_line=1, text='("Hello world!")'
    )
    string_ast_node = ASTNode(type="string", start_line=1, end_line=1, text='"Hello world!"')

    found_argument_list_ast_node = False
    for kg_node in kg_nodes:
        if kg_node.node == argument_list_ast_node:
            found_argument_list_ast_node = True
    assert found_argument_list_ast_node

    found_string_ast_node = False
    for kg_node in kg_nodes:
        if kg_node.node == string_ast_node:
            found_string_ast_node = True
    assert found_string_ast_node

    # Test if some of the edges exists
    found_edge = False
    for kg_edge in kg_edges:
        if (
            kg_edge.source.node == argument_list_ast_node
            and kg_edge.target.node == string_ast_node
            and kg_edge.type == KnowledgeGraphEdgeType.parent_of
        ):
            found_edge = True
    assert found_edge


def test_build_text_file_graph():
    file_graph_builder = FileGraphBuilder(1000, 100, 10)

    parent_kg_node = KnowledgeGraphNode(0, None)
    next_node_id, kg_nodes, kg_edges = file_graph_builder.build_file_graph(
        parent_kg_node, test_project_paths.MD_FILE, 0
    )

    assert next_node_id == 2
    assert len(kg_nodes) == 2
    assert len(kg_edges) == 3

    # Test if some of the nodes exists
    text_node_1 = TextNode(
        text="# A\n\nText under header A.\n\n## B\n\nText under header B.\n\n## C\n\nText under header C.\n\n### D",
        start_line=1,
        end_line=13,
    )
    text_node_2 = TextNode(text="### D\n\nText under header D.", start_line=13, end_line=14)

    found_text_node_1 = False
    for kg_node in kg_nodes:
        if kg_node.node == text_node_1:
            found_text_node_1 = True
    assert found_text_node_1

    found_text_node_2 = False
    for kg_node in kg_nodes:
        if kg_node.node == text_node_2:
            found_text_node_2 = True
    assert found_text_node_2

    # Test if some of the edges exists
    found_edge = False
    for kg_edge in kg_edges:
        if (
            kg_edge.source.node == text_node_1
            and kg_edge.target.node == text_node_2
            and kg_edge.type == KnowledgeGraphEdgeType.next_chunk
        ):
            found_edge = True
    assert found_edge
