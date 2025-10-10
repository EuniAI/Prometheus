import functools
from typing import Mapping, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from prometheus.docker.base_container import BaseContainer
from prometheus.git.git_repository import GitRepository
from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.lang_graph.nodes.context_retrieval_subgraph_node import ContextRetrievalSubgraphNode
from prometheus.lang_graph.nodes.edit_message_node import EditMessageNode
from prometheus.lang_graph.nodes.edit_node import EditNode
from prometheus.lang_graph.nodes.final_patch_selection_node import FinalPatchSelectionNode
from prometheus.lang_graph.nodes.get_pass_regression_test_patch_subgraph_node import (
    GetPassRegressionTestPatchSubgraphNode,
)
from prometheus.lang_graph.nodes.git_diff_node import GitDiffNode
from prometheus.lang_graph.nodes.git_reset_node import GitResetNode
from prometheus.lang_graph.nodes.issue_bug_analyzer_message_node import IssueBugAnalyzerMessageNode
from prometheus.lang_graph.nodes.issue_bug_analyzer_node import IssueBugAnalyzerNode
from prometheus.lang_graph.nodes.issue_bug_context_message_node import IssueBugContextMessageNode
from prometheus.lang_graph.nodes.patch_normalization_node import PatchNormalizationNode
from prometheus.lang_graph.nodes.reset_messages_node import ResetMessagesNode
from prometheus.lang_graph.subgraphs.issue_not_verified_bug_state import IssueNotVerifiedBugState


class IssueNotVerifiedBugSubgraph:
    def __init__(
        self,
        advanced_model: BaseChatModel,
        base_model: BaseChatModel,
        kg: KnowledgeGraph,
        git_repo: GitRepository,
        container: BaseContainer,
        repository_id: int,
    ):
        issue_bug_context_message_node = IssueBugContextMessageNode()
        context_retrieval_subgraph_node = ContextRetrievalSubgraphNode(
            base_model=base_model,
            advanced_model=advanced_model,
            kg=kg,
            local_path=git_repo.playground_path,
            query_key_name="bug_fix_query",
            context_key_name="bug_fix_context",
            repository_id=repository_id,
        )

        issue_bug_analyzer_message_node = IssueBugAnalyzerMessageNode()
        issue_bug_analyzer_node = IssueBugAnalyzerNode(advanced_model)
        issue_bug_analyzer_tools = ToolNode(
            tools=issue_bug_analyzer_node.tools,
            name="issue_bug_analyzer_tools",
            messages_key="issue_bug_analyzer_messages",
        )

        edit_message_node = EditMessageNode()
        edit_node = EditNode(advanced_model, git_repo.playground_path, kg)
        edit_tools = ToolNode(
            tools=edit_node.tools,
            name="edit_tools",
            messages_key="edit_messages",
        )
        git_diff_node = GitDiffNode(git_repo, "edit_patches", return_list=True)

        git_reset_node = GitResetNode(git_repo)
        reset_issue_bug_analyzer_messages_node = ResetMessagesNode("issue_bug_analyzer_messages")
        reset_edit_messages_node = ResetMessagesNode("edit_messages")

        # Patch Normalization Node
        patch_normalization_node = PatchNormalizationNode("edit_patches", "final_candidate_patches")

        # Get pass regression test patch subgraph node
        get_pass_regression_test_patch_subgraph_node = GetPassRegressionTestPatchSubgraphNode(
            model=base_model,
            container=container,
            git_repo=git_repo,
            testing_patch_key="final_candidate_patches",
            is_testing_patch_list=True,
            return_str_patch=True,
            return_key="final_candidate_patches",
        )

        # Final patch selection node
        final_patch_selection_node = FinalPatchSelectionNode(
            advanced_model, "final_candidate_patches", "final_patch"
        )

        workflow = StateGraph(IssueNotVerifiedBugState)

        workflow.add_node("issue_bug_context_message_node", issue_bug_context_message_node)
        workflow.add_node("context_retrieval_subgraph_node", context_retrieval_subgraph_node)

        workflow.add_node("issue_bug_analyzer_message_node", issue_bug_analyzer_message_node)
        workflow.add_node("issue_bug_analyzer_node", issue_bug_analyzer_node)
        workflow.add_node("issue_bug_analyzer_tools", issue_bug_analyzer_tools)

        workflow.add_node("edit_message_node", edit_message_node)
        workflow.add_node("edit_node", edit_node)
        workflow.add_node("edit_tools", edit_tools)
        workflow.add_node("git_diff_node", git_diff_node)

        workflow.add_node("git_reset_node", git_reset_node)
        workflow.add_node(
            "reset_issue_bug_analyzer_messages_node", reset_issue_bug_analyzer_messages_node
        )
        workflow.add_node("reset_edit_messages_node", reset_edit_messages_node)

        workflow.add_node("patch_normalization_node", patch_normalization_node)

        workflow.add_node(
            "get_pass_regression_test_patch_subgraph_node",
            get_pass_regression_test_patch_subgraph_node,
        )

        workflow.add_node("final_patch_selection_node", final_patch_selection_node)

        workflow.set_entry_point("issue_bug_context_message_node")
        workflow.add_edge("issue_bug_context_message_node", "context_retrieval_subgraph_node")
        workflow.add_edge("context_retrieval_subgraph_node", "issue_bug_analyzer_message_node")
        workflow.add_edge("issue_bug_analyzer_message_node", "issue_bug_analyzer_node")

        # Conditionally invoke tools or continue to edit message
        workflow.add_conditional_edges(
            "issue_bug_analyzer_node",
            functools.partial(tools_condition, messages_key="issue_bug_analyzer_messages"),
            {"tools": "issue_bug_analyzer_tools", END: "edit_message_node"},
        )

        workflow.add_edge("issue_bug_analyzer_tools", "issue_bug_analyzer_node")

        workflow.add_edge("edit_message_node", "edit_node")
        workflow.add_conditional_edges(
            "edit_node",
            functools.partial(tools_condition, messages_key="edit_messages"),
            {"tools": "edit_tools", END: "git_diff_node"},
        )
        workflow.add_edge("edit_tools", "edit_node")

        workflow.add_conditional_edges(
            "git_diff_node",
            lambda state: len(state["edit_patches"]) < state["number_of_candidate_patch"],
            {
                True: "git_reset_node",
                False: "patch_normalization_node",
            },
        )
        workflow.add_conditional_edges(
            "patch_normalization_node",
            lambda state: state["run_regression_test"],
            {
                True: "get_pass_regression_test_patch_subgraph_node",
                False: "final_patch_selection_node",
            },
        )
        workflow.add_edge(
            "get_pass_regression_test_patch_subgraph_node", "final_patch_selection_node"
        )

        workflow.add_edge("git_reset_node", "reset_issue_bug_analyzer_messages_node")
        workflow.add_edge("reset_issue_bug_analyzer_messages_node", "reset_edit_messages_node")
        workflow.add_edge("reset_edit_messages_node", "issue_bug_analyzer_message_node")

        workflow.add_edge("final_patch_selection_node", END)

        self.subgraph = workflow.compile()

    def invoke(
        self,
        issue_title: str,
        issue_body: str,
        issue_comments: Sequence[Mapping[str, str]],
        number_of_candidate_patch: int,
        run_regression_test: bool,
        selected_regression_tests: Sequence[str],
    ):
        config = {"recursion_limit": number_of_candidate_patch * 60 + 60}

        input_state = {
            "issue_title": issue_title,
            "issue_body": issue_body,
            "issue_comments": issue_comments,
            "number_of_candidate_patch": number_of_candidate_patch,
            "max_refined_query_loop": 4,
            "run_regression_test": run_regression_test,
            "selected_regression_tests": selected_regression_tests,
        }

        output_state = self.subgraph.invoke(input_state, config)
        return {
            "final_patch": output_state["final_patch"],
        }
