import functools
from typing import Mapping, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from prometheus.docker.base_container import BaseContainer
from prometheus.git.git_repository import GitRepository
from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.lang_graph.nodes.bug_get_regression_tests_subgraph_node import (
    BugGetRegressionTestsSubgraphNode,
)
from prometheus.lang_graph.nodes.context_retrieval_subgraph_node import ContextRetrievalSubgraphNode
from prometheus.lang_graph.nodes.edit_message_node import EditMessageNode
from prometheus.lang_graph.nodes.edit_node import EditNode
from prometheus.lang_graph.nodes.final_patch_selection_node import FinalPatchSelectionNode
from prometheus.lang_graph.nodes.get_pass_regression_test_patch_subgraph_node import (
    GetPassRegressionTestPatchSubgraphNode,
)
from prometheus.lang_graph.nodes.git_diff_node import GitDiffNode
from prometheus.lang_graph.nodes.git_reset_node import GitResetNode
from prometheus.lang_graph.nodes.issue_feature_analyzer_message_node import (
    IssueFeatureAnalyzerMessageNode,
)
from prometheus.lang_graph.nodes.issue_feature_analyzer_node import IssueFeatureAnalyzerNode
from prometheus.lang_graph.nodes.issue_feature_context_message_node import (
    IssueFeatureContextMessageNode,
)
from prometheus.lang_graph.nodes.patch_normalization_node import PatchNormalizationNode
from prometheus.lang_graph.nodes.reset_messages_node import ResetMessagesNode
from prometheus.lang_graph.subgraphs.issue_feature_state import IssueFeatureState


class IssueFeatureSubgraph:
    """
    A LangGraph-based subgraph that handles feature request issues by generating,
    applying, and validating patch candidates.

    This subgraph executes the following phases:
    0. Optional regression test selection (if enabled)
    1. Context construction and retrieval from knowledge graph and codebase
    2. Semantic analysis of the feature request using advanced LLM
    3. Patch generation via LLM and optional tool invocations
    4. Patch application with Git diff visualization
    5. Optional regression test validation
    6. Iterative refinement if verification fails

    Attributes:
        subgraph (StateGraph): The compiled LangGraph workflow to handle feature requests.
    """

    def __init__(
        self,
        advanced_model: BaseChatModel,
        base_model: BaseChatModel,
        kg: KnowledgeGraph,
        git_repo: GitRepository,
        container: BaseContainer,
        repository_id: int,
    ):
        """
        Initialize the feature request subgraph.

        Args:
            advanced_model (BaseChatModel): A strong LLM used for feature analysis and patch generation.
            base_model (BaseChatModel): A smaller, less expensive LLM used for context retrieval and test verification.
            kg (KnowledgeGraph): A knowledge graph used for context-aware retrieval of relevant code entities.
            git_repo (GitRepository): Git interface to apply patches and get diffs.
            container (BaseContainer): A test container to run code validations.
            repository_id (int): Repository identifier for context retrieval.
        """

        # Phase 0: Select regression tests if enabled
        bug_get_regression_tests_subgraph_node = BugGetRegressionTestsSubgraphNode(
            advanced_model=advanced_model,
            base_model=base_model,
            container=container,
            kg=kg,
            git_repo=git_repo,
            repository_id=repository_id,
        )

        # Phase 1: Retrieve context related to the feature request
        issue_feature_context_message_node = IssueFeatureContextMessageNode()
        context_retrieval_subgraph_node = ContextRetrievalSubgraphNode(
            base_model=base_model,
            advanced_model=advanced_model,
            kg=kg,
            local_path=git_repo.playground_path,
            query_key_name="feature_query",
            context_key_name="feature_context",
            repository_id=repository_id,
        )

        # Phase 2: Analyze the feature request and generate implementation plan
        issue_feature_analyzer_message_node = IssueFeatureAnalyzerMessageNode()
        issue_feature_analyzer_node = IssueFeatureAnalyzerNode(advanced_model)
        issue_feature_analyzer_tools = ToolNode(
            tools=issue_feature_analyzer_node.tools,
            name="issue_feature_analyzer_tools",
            messages_key="issue_feature_analyzer_messages",
        )

        # Phase 3: Generate code edits and optionally apply toolchains
        edit_message_node = EditMessageNode(
            context_key="feature_context", analyzer_message_key="issue_feature_analyzer_messages"
        )
        edit_node = EditNode(advanced_model, git_repo.playground_path, kg)
        edit_tools = ToolNode(
            tools=edit_node.tools,
            name="edit_tools",
            messages_key="edit_messages",
        )
        git_diff_node = GitDiffNode(git_repo, "edit_patches", return_list=True)

        git_reset_node = GitResetNode(git_repo)
        reset_issue_feature_analyzer_messages_node = ResetMessagesNode(
            "issue_feature_analyzer_messages"
        )
        reset_edit_messages_node = ResetMessagesNode("edit_messages")

        # Phase 4: Patch Normalization
        patch_normalization_node = PatchNormalizationNode("edit_patches", "final_candidate_patches")

        # Phase 5: Optional regression test validation
        get_pass_regression_test_patch_subgraph_node = GetPassRegressionTestPatchSubgraphNode(
            model=base_model,
            container=container,
            git_repo=git_repo,
            testing_patch_key="final_candidate_patches",
            is_testing_patch_list=True,
            return_str_patch=True,
            return_key="final_candidate_patches",
        )

        # Phase 6: Final patch selection
        final_patch_selection_node = FinalPatchSelectionNode(
            advanced_model, "final_candidate_patches", "final_patch", "feature_context"
        )

        # Build the LangGraph workflow
        workflow = StateGraph(IssueFeatureState)

        workflow.add_node(
            "bug_get_regression_tests_subgraph_node", bug_get_regression_tests_subgraph_node
        )
        workflow.add_node("issue_feature_context_message_node", issue_feature_context_message_node)
        workflow.add_node("context_retrieval_subgraph_node", context_retrieval_subgraph_node)

        workflow.add_node(
            "issue_feature_analyzer_message_node", issue_feature_analyzer_message_node
        )
        workflow.add_node("issue_feature_analyzer_node", issue_feature_analyzer_node)
        workflow.add_node("issue_feature_analyzer_tools", issue_feature_analyzer_tools)

        workflow.add_node("edit_message_node", edit_message_node)
        workflow.add_node("edit_node", edit_node)
        workflow.add_node("edit_tools", edit_tools)
        workflow.add_node("git_diff_node", git_diff_node)

        workflow.add_node("git_reset_node", git_reset_node)
        workflow.add_node(
            "reset_issue_feature_analyzer_messages_node", reset_issue_feature_analyzer_messages_node
        )
        workflow.add_node("reset_edit_messages_node", reset_edit_messages_node)

        workflow.add_node("patch_normalization_node", patch_normalization_node)

        workflow.add_node(
            "get_pass_regression_test_patch_subgraph_node",
            get_pass_regression_test_patch_subgraph_node,
        )

        workflow.add_node("final_patch_selection_node", final_patch_selection_node)

        # Define edges for full flow
        # Start with bug_get_regression_tests_subgraph_node if regression tests are to be run,
        # otherwise start with issue_feature_context_message_node
        workflow.set_conditional_entry_point(
            lambda state: "bug_get_regression_tests_subgraph_node"
            if state["run_regression_test"]
            else "issue_feature_context_message_node",
            {
                "bug_get_regression_tests_subgraph_node": "bug_get_regression_tests_subgraph_node",
                "issue_feature_context_message_node": "issue_feature_context_message_node",
            },
        )
        # Add edge from regression test selection to context retrieval
        workflow.add_edge(
            "bug_get_regression_tests_subgraph_node", "issue_feature_context_message_node"
        )
        workflow.add_edge("issue_feature_context_message_node", "context_retrieval_subgraph_node")
        workflow.add_edge("context_retrieval_subgraph_node", "issue_feature_analyzer_message_node")
        workflow.add_edge("issue_feature_analyzer_message_node", "issue_feature_analyzer_node")

        # Conditionally invoke tools or continue to edit message
        workflow.add_conditional_edges(
            "issue_feature_analyzer_node",
            functools.partial(tools_condition, messages_key="issue_feature_analyzer_messages"),
            {"tools": "issue_feature_analyzer_tools", END: "edit_message_node"},
        )

        workflow.add_edge("issue_feature_analyzer_tools", "issue_feature_analyzer_node")

        workflow.add_edge("edit_message_node", "edit_node")
        workflow.add_conditional_edges(
            "edit_node",
            functools.partial(tools_condition, messages_key="edit_messages"),
            {"tools": "edit_tools", END: "git_diff_node"},
        )
        workflow.add_edge("edit_tools", "edit_node")

        # Check if we need more patches or proceed to normalization
        workflow.add_conditional_edges(
            "git_diff_node",
            lambda state: len(state["edit_patches"]) < state["number_of_candidate_patch"],
            {
                True: "git_reset_node",
                False: "patch_normalization_node",
            },
        )

        # If regression tests are enabled, run them; otherwise go to final patch selection
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

        # Reset messages and loop back to generate more patches
        workflow.add_edge("git_reset_node", "reset_issue_feature_analyzer_messages_node")
        workflow.add_edge("reset_issue_feature_analyzer_messages_node", "reset_edit_messages_node")
        workflow.add_edge("reset_edit_messages_node", "issue_feature_analyzer_message_node")

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
        """
        Invoke the feature request subgraph.

        Args:
            issue_title: Title of the feature request issue
            issue_body: Detailed description of the feature request
            issue_comments: Additional comments on the issue
            number_of_candidate_patch: Number of patch candidates to generate
            run_regression_test: Whether to run regression tests
            selected_regression_tests: List of selected regression tests to run

        Returns:
            Dictionary containing the final patch
        """
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
