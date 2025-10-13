from langchain_core.messages import HumanMessage

from prometheus.lang_graph.nodes.add_context_refined_query_message_node import (
    AddContextRefinedQueryMessageNode,
)
from prometheus.models.query import Query


def test_add_context_refined_query_message_node_with_all_fields():
    """Test node with all fields populated in refined_query."""
    node = AddContextRefinedQueryMessageNode()

    refined_query = Query(
        essential_query="Find all authentication logic",
        extra_requirements="Include error handling and validation",
        purpose="Security audit",
    )

    state = {"refined_query": refined_query}

    result = node(state)

    assert "context_provider_messages" in result
    assert len(result["context_provider_messages"]) == 1
    assert isinstance(result["context_provider_messages"][0], HumanMessage)

    message_content = result["context_provider_messages"][0].content
    assert "Essential query: Find all authentication logic" in message_content
    assert "Extra requirements: Include error handling and validation" in message_content
    assert "Purpose: Security audit" in message_content


def test_add_context_refined_query_message_node_essential_query_only():
    """Test node with only essential_query populated."""
    node = AddContextRefinedQueryMessageNode()

    refined_query = Query(
        essential_query="Locate the main entry point",
        extra_requirements="",
        purpose="",
    )

    state = {"refined_query": refined_query}

    result = node(state)

    assert "context_provider_messages" in result
    assert len(result["context_provider_messages"]) == 1

    message_content = result["context_provider_messages"][0].content
    assert "Essential query: Locate the main entry point" in message_content
    assert "Extra requirements:" not in message_content
    assert "Purpose:" not in message_content


def test_add_context_refined_query_message_node_with_extra_requirements_only():
    """Test node with essential_query and extra_requirements only."""
    node = AddContextRefinedQueryMessageNode()

    refined_query = Query(
        essential_query="Find database queries",
        extra_requirements="Focus on SQL injection vulnerabilities",
        purpose="",
    )

    state = {"refined_query": refined_query}

    result = node(state)

    assert "context_provider_messages" in result
    message_content = result["context_provider_messages"][0].content

    assert "Essential query: Find database queries" in message_content
    assert "Extra requirements: Focus on SQL injection vulnerabilities" in message_content
    assert "Purpose:" not in message_content


def test_add_context_refined_query_message_node_with_purpose_only():
    """Test node with essential_query and purpose only."""
    node = AddContextRefinedQueryMessageNode()

    refined_query = Query(
        essential_query="Identify all API endpoints",
        extra_requirements="",
        purpose="Documentation generation",
    )

    state = {"refined_query": refined_query}

    result = node(state)

    assert "context_provider_messages" in result
    message_content = result["context_provider_messages"][0].content

    assert "Essential query: Identify all API endpoints" in message_content
    assert "Extra requirements:" not in message_content
    assert "Purpose: Documentation generation" in message_content


def test_add_context_refined_query_message_node_returns_list():
    """Test that node returns a list with exactly one HumanMessage."""
    node = AddContextRefinedQueryMessageNode()

    refined_query = Query(
        essential_query="Test query",
        extra_requirements="Test requirements",
        purpose="Test purpose",
    )

    state = {"refined_query": refined_query}

    result = node(state)

    assert isinstance(result["context_provider_messages"], list)
    assert len(result["context_provider_messages"]) == 1
    assert isinstance(result["context_provider_messages"][0], HumanMessage)


def test_add_context_refined_query_message_node_message_format():
    """Test the exact format of the constructed message."""
    node = AddContextRefinedQueryMessageNode()

    refined_query = Query(
        essential_query="Query text",
        extra_requirements="Requirements text",
        purpose="Purpose text",
    )

    state = {"refined_query": refined_query}

    result = node(state)

    expected_content = (
        "Essential query: Query text\nExtra requirements: Requirements text\nPurpose: Purpose text"
    )

    assert result["context_provider_messages"][0].content == expected_content
