import functools
import math
from typing import Mapping, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from prometheus.docker.base_container import BaseContainer
from prometheus.git.git_repository import GitRepository
from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.lang_graph.nodes.bug_fix_verification_subgraph_node import (
    BugFixVerificationSubgraphNode,
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
from prometheus.lang_graph.nodes.issue_bug_analyzer_message_node import IssueBugAnalyzerMessageNode
from prometheus.lang_graph.nodes.issue_bug_analyzer_node import IssueBugAnalyzerNode
from prometheus.lang_graph.nodes.issue_bug_context_message_node import IssueBugContextMessageNode
from prometheus.lang_graph.nodes.noop_node import NoopNode
from prometheus.lang_graph.nodes.patch_normalization_node import PatchNormalizationNode
from prometheus.lang_graph.nodes.run_existing_tests_subgraph_node import (
    RunExistingTestsSubgraphNode,
)
from prometheus.lang_graph.subgraphs.issue_verified_bug_state import IssueVerifiedBugState


class IssueVerifiedBugSubgraph:
    """
    A LangGraph-based subgraph that handles verified bug issues by generating,
    applying, and validating patch candidates.

    This subgraph executes the following phases:
    1. Context construction and retrieval from knowledge graph and codebase
    2. Semantic analysis of the bug using advanced LLM
    3. Patch generation via LLM and optional tool invocations
    4. Patch application with Git diff visualization
    5. Build and test the modified code in a containerized environment
    6. Iterative refinement if verification fails

    Attributes:
        subgraph (StateGraph): The compiled LangGraph workflow to handle verified bugs.
    """

    def __init__(
        self,
        advanced_model: BaseChatModel,
        base_model: BaseChatModel,
        container: BaseContainer,
        kg: KnowledgeGraph,
        git_repo: GitRepository,
        repository_id: int,
    ):
        """
        Initialize the verified bug fix subgraph.

        Args:
            advanced_model (BaseChatModel): A strong LLM used for bug understanding and patch generation.
            base_model (BaseChatModel): A smaller, less expensive LLM used for context retrieval and test verification.
            container (BaseContainer): A test container to run code validations.
            kg (KnowledgeGraph): A knowledge graph used for context-aware retrieval of relevant code entities.
            git_repo (GitRepository): Git interface to apply patches and get diffs.
            neo4j_driver (neo4j.Driver): Neo4j driver for executing graph-based semantic queries.
        """

        # Phase 1: Retrieve context related to the bug
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

        # Phase 2: Analyze the bug and generate hypotheses
        issue_bug_analyzer_message_node = IssueBugAnalyzerMessageNode()
        issue_bug_analyzer_node = IssueBugAnalyzerNode(advanced_model)
        issue_bug_analyzer_tools = ToolNode(
            tools=issue_bug_analyzer_node.tools,
            name="issue_bug_analyzer_tools",
            messages_key="issue_bug_analyzer_messages",
        )

        # Phase 3: Generate code edits and optionally apply toolchains
        edit_message_node = EditMessageNode(
            context_key="bug_fix_context", analyzer_message_key="issue_bug_analyzer_messages"
        )
        edit_node = EditNode(advanced_model, git_repo.playground_path, kg)
        edit_tools = ToolNode(
            tools=edit_node.tools,
            name="edit_tools",
            messages_key="edit_messages",
        )

        # Phase 4: Generate the patch and reset the repository
        git_diff_node = GitDiffNode(git_repo, "edit_patch")
        git_reset_node = GitResetNode(git_repo)

        # Phase 5: Run Regression Tests if available
        get_pass_regression_test_patch_branch_node = NoopNode()
        get_pass_regression_test_patch_subgraph_node = GetPassRegressionTestPatchSubgraphNode(
            base_model=base_model,
            advanced_model=advanced_model,
            container=container,
            git_repo=git_repo,
            testing_patch_key="edit_patch",
            is_testing_patch_list=False,
            return_str_patch=False,
            return_key="tested_patch_result",
        )

        # Phase 6: Re-run test case that reproduces the bug
        bug_fix_verification_subgraph_node = BugFixVerificationSubgraphNode(
            base_model, container, git_repo
        )

        # Select the best patch if the number of passed reproduction test patches >= candidate patches
        final_patch_selection_branch_node = NoopNode()

        # Patch Normalization Node
        patch_normalization_node = PatchNormalizationNode(
            "pass_reproduction_test_patches", "final_candidate_patches"
        )

        final_patch_selection_node = FinalPatchSelectionNode(
            advanced_model, "final_candidate_patches", "edit_patch", "bug_fix_context"
        )

        # Phase 7: Optionally run existing tests
        run_existing_tests_branch_node = NoopNode()
        run_existing_tests_subgraph_node = RunExistingTestsSubgraphNode(
            model=base_model,
            container=container,
            git_repo=git_repo,
            testing_patch_key="edit_patch",
            existing_test_fail_log_key="existing_test_fail_log",
        )

        # Build the LangGraph workflow
        workflow = StateGraph(IssueVerifiedBugState)

        # Add nodes to graph
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
        workflow.add_node("bug_fix_verification_subgraph_node", bug_fix_verification_subgraph_node)

        workflow.add_node("final_patch_selection_branch_node", final_patch_selection_branch_node)
        workflow.add_node("patch_normalization_node", patch_normalization_node)
        workflow.add_node("final_patch_selection_node", final_patch_selection_node)

        workflow.add_node(
            "get_pass_regression_test_patch_branch_node", get_pass_regression_test_patch_branch_node
        )

        workflow.add_node(
            "get_pass_regression_test_patch_subgraph_node",
            get_pass_regression_test_patch_subgraph_node,
        )

        workflow.add_node("run_existing_tests_branch_node", run_existing_tests_branch_node)
        workflow.add_node("run_existing_tests_subgraph_node", run_existing_tests_subgraph_node)

        # Define edges for full flow
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

        # Conditionally invoke tools or continue to diffing
        workflow.add_conditional_edges(
            "edit_node",
            functools.partial(tools_condition, messages_key="edit_messages"),
            {"tools": "edit_tools", END: "git_diff_node"},
        )
        workflow.add_edge("edit_tools", "edit_node")

        # Generate the patch and reset the repository
        workflow.add_edge("git_diff_node", "git_reset_node")
        workflow.add_conditional_edges(
            "git_reset_node",
            lambda state: bool(state["edit_patch"]),
            {True: "bug_fix_verification_subgraph_node", False: "issue_bug_analyzer_message_node"},
        )

        # If reproduction test fails, loop back to reanalyze the bug
        workflow.add_conditional_edges(
            "bug_fix_verification_subgraph_node",
            lambda state: bool(state["reproducing_test_fail_log"]),
            {
                True: "issue_bug_analyzer_message_node",
                False: "final_patch_selection_branch_node",
            },
        )

        # If the number of passed reproduction test patches >= candidate patches, select the best patch
        workflow.add_conditional_edges(
            "final_patch_selection_branch_node",
            lambda state: len(state["pass_reproduction_test_patches"])
            >= state["number_of_candidate_patch"],
            {
                True: "patch_normalization_node",
                False: "get_pass_regression_test_patch_branch_node",
            },
        )

        workflow.add_edge("patch_normalization_node", "final_patch_selection_node")
        workflow.add_edge("final_patch_selection_node", END)

        # If selected regression tests are required to run, run them
        workflow.add_conditional_edges(
            "get_pass_regression_test_patch_branch_node",
            lambda state: state["run_regression_test"],
            {
                True: "get_pass_regression_test_patch_subgraph_node",
                False: "run_existing_tests_branch_node",
            },
        )

        workflow.add_conditional_edges(
            "get_pass_regression_test_patch_subgraph_node",
            lambda state: state["tested_patch_result"][0].passed,
            {
                True: "run_existing_tests_branch_node",
                False: "issue_bug_analyzer_message_node",
            },
        )

        # Optionally run existing tests suite
        workflow.add_conditional_edges(
            "run_existing_tests_branch_node",
            lambda state: state["run_existing_test"],
            {True: "run_existing_tests_subgraph_node", False: END},
        )

        # If test fail, go back to reanalyze and patch
        workflow.add_conditional_edges(
            "run_existing_tests_subgraph_node",
            lambda state: bool(state["existing_test_fail_log"]),
            {True: "issue_bug_analyzer_message_node", False: END},
        )

        # Compile and assign the subgraph
        self.subgraph = workflow.compile()

    def invoke(
        self,
        issue_title: str,
        issue_body: str,
        issue_comments: Sequence[Mapping[str, str]],
        number_of_candidate_patch: int,
        run_regression_test: bool,
        run_existing_test: bool,
        reproduced_bug_file: str,
        reproduced_bug_commands: Sequence[str],
        reproduced_bug_patch: str,
        selected_regression_tests: Sequence[str],
    ):
        """
        Invoke the verified bug fix subgraph.
        """
        # Set recursion limit based on number of candidate patches
        # (The number of candidate patches is halved for cost efficiency)

        number_of_candidate_patch_for_verified = math.ceil(number_of_candidate_patch / 2)

        config = {"recursion_limit": (number_of_candidate_patch_for_verified + 2) * 75}

        input_state = {
            "issue_title": issue_title,
            "issue_body": issue_body,
            "issue_comments": issue_comments,
            "number_of_candidate_patch": number_of_candidate_patch_for_verified,
            "run_regression_test": run_regression_test,
            "run_existing_test": run_existing_test,
            "reproduced_bug_file": reproduced_bug_file,
            "reproduced_bug_commands": reproduced_bug_commands,
            "reproduced_bug_patch": reproduced_bug_patch,
            "selected_regression_tests": selected_regression_tests,
            "max_refined_query_loop": 2,
        }

        output_state = self.subgraph.invoke(input_state, config)
        return {
            "edit_patch": output_state["edit_patch"],
        }
