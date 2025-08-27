import pytest
from langchain_core.messages import AIMessage, ToolMessage

from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.lang_graph.nodes.context_provider_node import ContextProviderNode
from tests.test_utils import test_project_paths
from tests.test_utils.util import FakeListChatWithToolsModel


@pytest.fixture(scope="function")
async def knowledge_graph_fixture():
    kg = KnowledgeGraph(1000, 100, 10, 0)
    await kg.build_graph(test_project_paths.TEST_PROJECT_PATH)
    return kg


@pytest.mark.slow
async def test_context_provider_node_basic_query(knowledge_graph_fixture):
    """Test basic query handling with the ContextProviderNode."""
    fake_response = "Fake response"
    fake_llm = FakeListChatWithToolsModel(responses=[fake_response])
    node = ContextProviderNode(
        model=fake_llm,
        kg=knowledge_graph_fixture,
        local_path=test_project_paths.TEST_PROJECT_PATH,
    )

    test_messages = [
        AIMessage(content="This code handles file processing"),
        ToolMessage(content="Found implementation in utils.py", tool_call_id="test_tool_call_1"),
    ]
    test_state = {
        "original_query": "How does the error handling work?",
        "context_provider_messages": test_messages,
    }

    result = node(test_state)

    assert "context_provider_messages" in result
    assert len(result["context_provider_messages"]) == 1
    assert result["context_provider_messages"][0].content == fake_response
