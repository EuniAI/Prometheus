"""Exercise keyless search through the analyzer's real tool and MCP transports."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.prebuilt import ToolNode

from prometheus.configuration.config import Settings
from prometheus.exceptions.web_search_tool_exception import WebSearchToolException
from prometheus.lang_graph.nodes.issue_bug_analyzer_node import IssueBugAnalyzerNode
from prometheus.lang_graph.nodes.issue_documentation_analyzer_node import (
    IssueDocumentationAnalyzerNode,
)
from prometheus.lang_graph.nodes.issue_feature_analyzer_node import IssueFeatureAnalyzerNode
from prometheus.lang_graph.nodes.issue_question_analyzer_node import IssueQuestionAnalyzerNode
from prometheus.tools import web_search


@pytest.fixture
def search_settings(monkeypatch):
    config = SimpleNamespace(
        WEB_SEARCH_PROVIDER="auto", TAVILY_API_KEY=None, WEB_SEARCH_TIMEOUT=2.0
    )
    monkeypatch.setattr(web_search, "settings", config)
    return config


@pytest.fixture
def mcp_transport(monkeypatch):
    """Keep the SDK protocol and request headers, replacing only HTTP I/O."""
    requests = []
    response = {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "results": [
                            {
                                "title": "Python errors",
                                "url": "https://docs.python.org/3/tutorial/errors.html",
                                "excerpts": ["Exceptions can be handled with try and except."],
                            }
                        ]
                    }
                ),
            }
        ],
        "isError": False,
    }

    async def handle(request):
        requests.append(request)
        if request.method != "POST":
            return httpx.Response(405)
        if "_http_status" in response:
            return httpx.Response(response["_http_status"], text="fixture HTTP failure")
        payload = json.loads(request.content)
        method = payload["method"]
        if "id" not in payload:
            return httpx.Response(202)
        if method == "initialize":
            result = {
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fixture", "version": "1"},
            }
        elif method == "tools/list":
            result = {"tools": [{"name": "web_search", "inputSchema": {"type": "object"}}]}
        else:
            assert method == "tools/call"
            result = response
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": payload["id"], "result": result})

    original = web_search.streamablehttp_client

    def connect(url, **kwargs):
        def factory(headers=None, timeout=None, auth=None):
            return httpx.AsyncClient(
                headers=headers,
                timeout=timeout,
                auth=auth,
                transport=httpx.MockTransport(handle),
                follow_redirects=True,
            )

        return original(url, **kwargs, httpx_client_factory=factory)

    monkeypatch.setattr(web_search, "streamablehttp_client", connect)
    return requests, response


def model():
    llm = Mock()
    llm.bind_tools.return_value = llm
    return llm


def test_fresh_settings_without_search_credentials(monkeypatch):
    # Supply unrelated required application settings while isolating dotenv and search credentials.
    for name in ("PROMETHEUS_TAVILY_API_KEY", "PROMETHEUS_WEB_SEARCH_PROVIDER"):
        monkeypatch.delenv(name, raising=False)
    values = {
        name: "fixture" for name, field in Settings.model_fields.items() if field.is_required()
    }
    values.update(
        ENVIRONMENT="local",
        BACKEND_CORS_ORIGINS=[],
        ENABLE_AUTHENTICATION=False,
        LOGGING_LEVEL="INFO",
        NEO4J_BATCH_SIZE=1,
        KNOWLEDGE_GRAPH_MAX_AST_DEPTH=1,
        KNOWLEDGE_GRAPH_CHUNK_SIZE=100,
        KNOWLEDGE_GRAPH_CHUNK_OVERLAP=1,
    )
    config = Settings(_env_file=None, **values)
    assert config.TAVILY_API_KEY is None
    assert config.WEB_SEARCH_PROVIDER == "auto"


def test_analyzer_dispatch_and_consumption(search_settings, mcp_transport):
    requests, _ = mcp_transport
    llm = model()
    node = IssueBugAnalyzerNode(llm)
    assert node.web_search_tool.provider == "parallel"
    llm.invoke.side_effect = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "web_search",
                    "args": {"query": "Python ValueError exception handling"},
                    "id": "s1",
                }
            ],
        ),
        AIMessage(content="Use try and except based on the documentation."),
    ]
    initial = HumanMessage(content="Analyze this error")
    state = node({"issue_bug_analyzer_messages": [initial]})
    dispatched = ToolNode(node.tools, messages_key="issue_bug_analyzer_messages").invoke(state)
    result = dispatched["issue_bug_analyzer_messages"][0]
    assert isinstance(result, ToolMessage)
    assert "https://docs.python.org/3/tutorial/errors.html" in result.content
    assert "Exceptions can be handled" in result.content
    final = node(
        {"issue_bug_analyzer_messages": [initial, *state["issue_bug_analyzer_messages"], result]}
    )
    assert "Use try and except" in final["issue_bug_analyzer_messages"][0].content
    assert llm.invoke.call_args.args[0][-1] is result
    calls = [json.loads(r.content) for r in requests if r.method == "POST"]
    assert {c["method"] for c in calls} >= {"initialize", "tools/call"}
    call = next(c for c in calls if c["method"] == "tools/call")
    assert call["params"] == {
        "name": "web_search",
        "arguments": {
            "objective": "Python ValueError exception handling",
            "search_queries": ["Python ValueError exception handling"],
        },
    }
    for request in requests:
        assert str(request.url) == "https://search.parallel.ai/mcp"
        assert (
            request.headers["user-agent"]
            == "Prometheus/1.3 (+https://github.com/EuniAI/Prometheus)"
        )
        assert "authorization" not in request.headers


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "node_class",
    [
        IssueBugAnalyzerNode,
        IssueFeatureAnalyzerNode,
        IssueDocumentationAnalyzerNode,
        IssueQuestionAnalyzerNode,
    ],
)
async def test_async_tool_dispatch(search_settings, mcp_transport, node_class):
    node = node_class(model())
    result = await node.tools[0].ainvoke({"query": "Python ValueError exception handling"})
    assert "https://docs.python.org/3/tutorial/errors.html" in result


@pytest.mark.parametrize(
    "provider,key,expected",
    [
        ("auto", "saved-key", "tavily"),
        ("auto", "", "parallel"),
        ("parallel", "saved-key", "parallel"),
        ("tavily", None, "tavily"),
        ("disabled", "saved-key", "disabled"),
    ],
)
def test_provider_choices(search_settings, monkeypatch, provider, key, expected):
    search_settings.WEB_SEARCH_PROVIDER = provider
    search_settings.TAVILY_API_KEY = key
    tavily = Mock()
    monkeypatch.setattr(web_search, "TavilyClient", tavily)
    tool = web_search.WebSearchTool()
    assert tool.provider == expected
    assert tavily.called is (expected == "tavily" and bool(key))
    if provider == "tavily":
        with pytest.raises(WebSearchToolException, match="requires PROMETHEUS_TAVILY_API_KEY"):
            tool.web_search("Python errors")
        assert not tavily.called


@pytest.mark.parametrize(
    "node_class",
    [
        IssueBugAnalyzerNode,
        IssueFeatureAnalyzerNode,
        IssueDocumentationAnalyzerNode,
        IssueQuestionAnalyzerNode,
    ],
)
def test_disabled_has_no_tool_or_network(search_settings, monkeypatch, node_class):
    search_settings.WEB_SEARCH_PROVIDER = "disabled"
    connect = Mock(side_effect=AssertionError("network must not run"))
    monkeypatch.setattr(web_search, "streamablehttp_client", connect)
    llm = model()
    node = node_class(llm)
    assert node.tools == []
    llm.bind_tools.assert_not_called()
    with pytest.raises(WebSearchToolException, match="disabled"):
        node.web_search_tool.web_search("Python errors")
    connect.assert_not_called()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"include_domains": ["docs.python.org"]},
        {"exclude_domains": ["example.org"]},
        {"max_results": 2},
        {"max_results": 5},
    ],
)
def test_parallel_rejects_unsupported_settings(search_settings, monkeypatch, kwargs):
    connect = Mock(side_effect=AssertionError("network must not run"))
    monkeypatch.setattr(web_search, "streamablehttp_client", connect)
    with pytest.raises(WebSearchToolException, match="Select the tavily provider"):
        web_search.WebSearchTool().web_search("Python errors", **kwargs)
    connect.assert_not_called()


@pytest.mark.parametrize(
    "response,error",
    [
        (
            {
                "content": [{"type": "text", "text": "Anonymous search quota exceeded"}],
                "isError": True,
            },
            "quota",
        ),
        ({"content": [], "isError": False}, "no text results"),
    ],
)
def test_mcp_errors_do_not_fallback(search_settings, mcp_transport, monkeypatch, response, error):
    search_settings.WEB_SEARCH_PROVIDER = "parallel"
    search_settings.TAVILY_API_KEY = "saved-key"
    _, fixture_response = mcp_transport
    fixture_response.update(response)
    tavily = Mock(side_effect=AssertionError("no fallback"))
    monkeypatch.setattr(web_search, "TavilyClient", tavily)
    with pytest.raises(WebSearchToolException, match=error):
        IssueBugAnalyzerNode(model()).tools[0].invoke({"query": "Python errors"})
    tavily.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_timeout_and_cancellation_cleanup(search_settings, monkeypatch, cancel):
    from contextlib import asynccontextmanager

    started = asyncio.Event()
    closed = asyncio.Event()

    @asynccontextmanager
    async def stalled_transport(*args, **kwargs):
        try:
            started.set()
            await asyncio.Event().wait()
            yield
        finally:
            closed.set()

    search_settings.WEB_SEARCH_TIMEOUT = 0.05
    monkeypatch.setattr(web_search, "streamablehttp_client", stalled_transport)
    tool = IssueBugAnalyzerNode(model()).tools[0]
    task = asyncio.create_task(tool.ainvoke({"query": "Python errors"}))
    await started.wait()
    if cancel:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        with pytest.raises(WebSearchToolException, match="timed out"):
            await task
    assert closed.is_set()


def test_transport_failure_is_safe(search_settings, monkeypatch):
    monkeypatch.setattr(
        web_search, "streamablehttp_client", Mock(side_effect=OSError("private detail"))
    )
    with pytest.raises(WebSearchToolException, match="^Parallel Search MCP request failed$"):
        IssueBugAnalyzerNode(model()).tools[0].invoke({"query": "Python errors"})


@pytest.mark.parametrize("status", [401, 429, 500])
def test_http_errors(search_settings, mcp_transport, status):
    _, response = mcp_transport
    response["_http_status"] = status
    with pytest.raises(WebSearchToolException, match="^Parallel Search MCP request failed$"):
        IssueBugAnalyzerNode(model()).tools[0].invoke({"query": "Python errors"})


@pytest.mark.asyncio
async def test_saved_tavily_uses_normal_dispatch(search_settings, monkeypatch):
    search_settings.TAVILY_API_KEY = "saved-key"
    client = Mock()
    client.search.return_value = {
        "results": [
            {
                "title": "Python errors",
                "url": "https://docs.python.org/",
                "content": "Handle errors with try and except",
            }
        ]
    }
    factory = Mock(return_value=client)
    monkeypatch.setattr(web_search, "TavilyClient", factory)
    monkeypatch.setattr(
        web_search, "streamablehttp_client", Mock(side_effect=AssertionError("no MCP"))
    )
    node = IssueBugAnalyzerNode(model())
    result = await node.tools[0].ainvoke({"query": "Python errors"})
    assert "https://docs.python.org/" in result
    factory.assert_called_once_with(api_key="saved-key")
    assert client.search.call_args.kwargs["search_depth"] == "advanced"
    assert client.search.call_args.kwargs["max_results"] == 5
    assert "docs.python.org" in client.search.call_args.kwargs["include_domains"]
