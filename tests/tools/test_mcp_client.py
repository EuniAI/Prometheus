import asyncio
from typing import (
    Union,
    cast,
)

from langchain_core.messages import (
    ToolCall,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.errors import GraphInterrupt
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.prebuilt.tool_node import (
    _handle_tool_error,
    _infer_handled_types,
    msg_content_output,
)

from prometheus.app.services.llm_service import get_model

# 使用真实模型进行工具调用
from prometheus.configuration.config import settings

# 创建自定义 ToolNode
preset_params = {
    "tavily-search": {
        "include_domains": ["pypi.org", "docs.python.org"],
        "exclude_domains": [
            "stackoverflow.com",
            "*huggingface*",
            "discourse.slicer.org",
            "ask.csdn.net",
            "codepudding.com",
            "*geeksforgeeks*",
            "*github*",
            "forum.developer.parrot.com",
        ],
    }
}


class CustomToolNode(ToolNode):
    """自定义 ToolNode，支持为特定工具添加预设参数"""

    def __init__(self, tools, preset_params=None, **kwargs):
        super().__init__(tools, **kwargs)
        self.preset_params = preset_params or {}

    async def _arun_one(self, call: ToolCall, config: RunnableConfig) -> ToolMessage:
        if invalid_tool_message := self._validate_tool_call(call):
            return invalid_tool_message

        try:
            # 构建基础输入
            input = {**call, **{"type": "tool_call"}}

            # 如果这个工具有预设参数，则添加到输入中
            if call["name"] in self.preset_params:
                preset_for_tool = self.preset_params[call["name"]]
                # 预设参数优先级较低，不会覆盖用户传递的参数
                merged_args = {**preset_for_tool, **call.get("args", {})}
                input["args"] = merged_args
                print(f"🔧 为工具 {call['name']} 添加预设参数: {preset_for_tool}")
                print(f"🔧 最终参数: {merged_args}")

            tool_message: ToolMessage = await self.tools_by_name[call["name"]].ainvoke(
                input, config
            )
            tool_message.content = cast(Union[str, list], msg_content_output(tool_message.content))
            return tool_message
        except GraphInterrupt as e:
            raise e
        except Exception as e:
            # 使用父类的错误处理逻辑
            if isinstance(self.handle_tool_errors, tuple):
                handled_types: tuple = self.handle_tool_errors
            elif callable(self.handle_tool_errors):
                handled_types = _infer_handled_types(self.handle_tool_errors)
            else:
                handled_types = (Exception,)

            if not self.handle_tool_errors or not isinstance(e, handled_types):
                raise e
            else:
                content = _handle_tool_error(e, flag=self.handle_tool_errors)
                return ToolMessage(
                    content=content, name=call["name"], tool_call_id=call["id"], status="error"
                )


async def main():
    # 获取 Tavily API key
    tavily_api_key = settings.get("TAVILY_API_KEY", None)
    if tavily_api_key is None:
        print("错误: 未设置 TAVILY_API_KEY")
        return

    model = get_model(
        "gpt-4o-mini",
        openai_format_api_key=settings.get("OPENAI_FORMAT_API_KEY", None),
        openai_format_base_url=settings.get("OPENAI_FORMAT_BASE_URL", None),
        anthropic_api_key=None,
        gemini_api_key=None,
        temperature=0.0,
        max_output_tokens=15000,
    )

    async def init_tool():
        # 使用 HTTP 传输直接连接到 Tavily MCP 服务器
        client = MultiServerMCPClient(
            {
                "tavily_web_search": {
                    "transport": "streamable_http",
                    "url": f"https://mcp.tavily.com/mcp/?tavilyApiKey={tavily_api_key}",
                }
            }
        )

        # 异步获取工具
        tools = await client.get_tools()
        print(f"获取到的工具: {[tool.name for tool in tools]}")
        # for tool in tools:
        #     print(f"\n工具名称: {tool.name}")
        #     if hasattr(tool, 'args_schema') and tool.args_schema:
        #         properties = tool.args_schema.get('properties', {})
        #         # 简单的正则匹配设置默认值
        #         for param_name in properties.keys():
        #             param_lower = param_name.lower()
        #             if re.search(r'include.*domain', param_lower):
        #                 properties[param_name]['default'] = ["pypi.org", "docs.python.org"]
        #                 print(f"  ✅ 设置 {param_name} 默认值: include domains")
        #             elif re.search(r'exclude.*domain', param_lower):
        #                 properties[param_name]['default'] = ["stackoverflow.com", "*huggingface", "discourse.slicer.org","ask.csdn.net",
        #                     "codepudding.com", "*geeksforgeeks*", "*github*", "forum.developer.parrot.com"]
        #                 print(f"  ✅ 设置 {param_name} 默认值: exclude domains")

        #             elif re.search(r'search.*depth', param_lower):
        #                 properties[param_name]['default'] = "advanced"
        #                 print(f"  ✅ 设置 {param_name} 默认值: advanced")
        return tools

    tools = await init_tool()

    async def call_model(state: MessagesState):
        messages = state["messages"]
        print("\n=== call_model 被调用 ===")
        print(f"输入消息数量: {len(messages)}")

        print(f"可用工具: {[tool.name for tool in tools]}")

        # 使用真实模型调用，绑定预设参数的工具
        model_with_tools = model.bind_tools(tools)
        print("开始调用模型...")

        response = await model_with_tools.ainvoke(messages)
        print(f"模型响应类型: {type(response)}")

        return {"messages": [response]}

    # 创建工具节点
    builder = StateGraph(MessagesState)
    builder.add_node("call_model", call_model)
    # builder.add_node("tools", CustomToolNode(tools, preset_params=preset_params))
    builder.add_node("tools", ToolNode(tools))

    # 构建图
    builder.add_edge(START, "call_model")
    builder.add_conditional_edges(
        "call_model",
        tools_condition,
    )
    builder.add_edge("tools", "call_model")

    graph = builder.compile()

    # 执行测试 - 演示如何传递 include_domains 等参数
    # 注意：参数会在工具调用时由 LLM 自动传递，这里展示一个需要特定域名搜索的查询
    test_query = """
    ERROR: Could not find a version that satisfies the requirement opencv (from versions: none)
    ERROR: No matching distribution found for opencv
    报错
    """

    system_prompt = """\
    You are a web search assistant. When using the tavily_search tool, ALWAYS include these parameters:
    - exclude_domains: ["stackoverflow.com", "*huggingface*", "discourse.slicer.org","ask.csdn.net", "codepudding.com", "*geeksforgeeks*", "*github*", "forum.developer.parrot.com"]
    - include_domains: ['pypi.org', 'docs.python.org']
    - search_depth: "advanced"
    
    Make sure to explicitly pass these parameters in your tool call.
    """
    # system_prompt = """\
    # You are a web search assistant. help the human to find the answer to the question.
    # """

    response = await graph.ainvoke({"messages": system_prompt + "\n" + test_query})
    # print("Response:", response)

    return response


# 运行异步主函数
if __name__ == "__main__":
    result = asyncio.run(main())
    print(result["messages"][-1].content)
