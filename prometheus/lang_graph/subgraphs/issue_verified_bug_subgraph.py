import functools
from typing import Mapping, Optional, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from prometheus.docker.base_container import BaseContainer
from prometheus.git.git_repository import GitRepository
from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.lang_graph.nodes.bug_fix_verification_subgraph_node import (
    BugFixVerificationSubgraphNode,
)
from prometheus.lang_graph.nodes.build_and_test_subgraph_node import BuildAndTestSubgraphNode
from prometheus.lang_graph.nodes.context_retrieval_subgraph_node import ContextRetrievalSubgraphNode
from prometheus.lang_graph.nodes.edit_message_node import EditMessageNode
from prometheus.lang_graph.nodes.edit_node import EditNode
from prometheus.lang_graph.nodes.get_pass_regression_test_patch_subgraph_node import (
    GetPassRegressionTestPatchSubgraphNode,
)
from prometheus.lang_graph.nodes.git_diff_node import GitDiffNode
from prometheus.lang_graph.nodes.git_reset_node import GitResetNode
from prometheus.lang_graph.nodes.issue_bug_analyzer_message_node import IssueBugAnalyzerMessageNode
from prometheus.lang_graph.nodes.issue_bug_analyzer_node import IssueBugAnalyzerNode
from prometheus.lang_graph.nodes.issue_bug_context_message_node import IssueBugContextMessageNode
from prometheus.lang_graph.nodes.noop_node import NoopNode
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
        build_commands: Optional[Sequence[str]] = None,
        test_commands: Optional[Sequence[str]] = None,
    ):
        """
        Initialize the verified bug fix subgraph.

        Args:
            advanced_model (BaseChatModel): A strong LLM used for bug understanding and patch generation.
            base_model (BaseChatModel): A smaller, less expensive LLM used for context retrieval and test verification.
            container (BaseContainer): A build/test container to run code validations.
            kg (KnowledgeGraph): A knowledge graph used for context-aware retrieval of relevant code entities.
            git_repo (GitRepository): Git interface to apply patches and get diffs.
            neo4j_driver (neo4j.Driver): Neo4j driver for executing graph-based semantic queries.
            build_commands (Optional[Sequence[str]]): Commands to build the project inside the container.
            test_commands (Optional[Sequence[str]]): Commands to test the project inside the container.
        """

        # Phase 1: Retrieve context related to the bug
        issue_bug_context_message_node = IssueBugContextMessageNode()
        context_retrieval_subgraph_node = ContextRetrievalSubgraphNode(
            model=base_model,
            kg=kg,
            local_path=git_repo.playground_path,
            query_key_name="bug_fix_query",
            context_key_name="bug_fix_context",
        )

        # Phase 2: Analyze the bug and generate hypotheses
        issue_bug_analyzer_message_node = IssueBugAnalyzerMessageNode()
        issue_bug_analyzer_node = IssueBugAnalyzerNode(advanced_model)

        # Phase 3: Generate code edits and optionally apply toolchains
        edit_message_node = EditMessageNode()
        edit_node = EditNode(advanced_model, git_repo.playground_path)
        edit_tools = ToolNode(
            tools=edit_node.tools,
            name="edit_tools",
            messages_key="edit_messages",
        )

        # Phase 4: Generate the patch and reset the repository
        git_diff_node = GitDiffNode(git_repo, "edit_patch")
        git_reset_node = GitResetNode(git_repo)

        noop_node = NoopNode()

        # Phase 5: Run Regression Tests if available
        get_pass_regression_test_patch_subgraph_node = GetPassRegressionTestPatchSubgraphNode(
            model=base_model,
            container=container,
            git_repo=git_repo,
            testing_patch_key="edit_patch",
            is_testing_patch_list=False,
        )

        # Phase 6: Re-run test case that reproduces the bug
        bug_fix_verification_subgraph_node = BugFixVerificationSubgraphNode(
            base_model, container, git_repo
        )

        # Phase 7: Optionally run full build and test after fix
        build_or_test_branch_node = NoopNode()
        build_and_test_subgraph_node = BuildAndTestSubgraphNode(
            container,
            advanced_model,
            kg,
            build_commands,
            test_commands,
        )

        # Build the LangGraph workflow
        workflow = StateGraph(IssueVerifiedBugState)

        # Add nodes to graph
        workflow.add_node("issue_bug_context_message_node", issue_bug_context_message_node)
        workflow.add_node("context_retrieval_subgraph_node", context_retrieval_subgraph_node)

        workflow.add_node("issue_bug_analyzer_message_node", issue_bug_analyzer_message_node)
        workflow.add_node("issue_bug_analyzer_node", issue_bug_analyzer_node)

        workflow.add_node("edit_message_node", edit_message_node)
        workflow.add_node("edit_node", edit_node)
        workflow.add_node("edit_tools", edit_tools)
        workflow.add_node("git_diff_node", git_diff_node)
        workflow.add_node("git_reset_node", git_reset_node)
        workflow.add_node("noop_node", noop_node)

        workflow.add_node(
            "get_pass_regression_test_patch_subgraph_node",
            get_pass_regression_test_patch_subgraph_node,
        )

        workflow.add_node("bug_fix_verification_subgraph_node", bug_fix_verification_subgraph_node)
        workflow.add_node("build_or_test_branch_node", build_or_test_branch_node)
        workflow.add_node("build_and_test_subgraph_node", build_and_test_subgraph_node)

        # Define edges for full flow
        workflow.set_entry_point("issue_bug_context_message_node")
        workflow.add_edge("issue_bug_context_message_node", "context_retrieval_subgraph_node")
        workflow.add_edge("context_retrieval_subgraph_node", "issue_bug_analyzer_message_node")
        workflow.add_edge("issue_bug_analyzer_message_node", "issue_bug_analyzer_node")
        workflow.add_edge("issue_bug_analyzer_node", "edit_message_node")
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
            {True: "noop_node", False: "issue_bug_analyzer_message_node"},
        )

        workflow.add_conditional_edges(
            "noop_node",
            lambda state: state["run_regression_test"],
            {
                True: "get_pass_regression_test_patch_subgraph_node",
                False: "bug_fix_verification_subgraph_node",
            },
        )
        workflow.add_conditional_edges(
            "get_pass_regression_test_patch_subgraph_node",
            lambda state: state["tested_patch_result"][0].passed,
            {
                True: "bug_fix_verification_subgraph_node",
                False: "issue_bug_analyzer_message_node",
            },
        )

        # If test still fails, loop back to reanalyze the bug
        workflow.add_conditional_edges(
            "bug_fix_verification_subgraph_node",
            lambda state: bool(state["reproducing_test_fail_log"]),
            {True: "issue_bug_analyzer_message_node", False: "build_or_test_branch_node"},
        )

        # Optionally run full build/test suite
        workflow.add_conditional_edges(
            "build_or_test_branch_node",
            lambda state: state["run_build"] or state["run_existing_test"],
            {True: "build_and_test_subgraph_node", False: END},
        )

        # If build/test fail, go back to reanalyze and patch
        workflow.add_conditional_edges(
            "build_and_test_subgraph_node",
            lambda state: bool(state["build_fail_log"]) or bool(state["existing_test_fail_log"]),
            {True: "issue_bug_analyzer_message_node", False: END},
        )

        # Compile and assign the subgraph
        self.subgraph = workflow.compile()

    def invoke(
        self,
        issue_title: str,
        issue_body: str,
        issue_comments: Sequence[Mapping[str, str]],
        run_build: bool,
        run_regression_test: bool,
        run_existing_test: bool,
        reproduced_bug_file: str,
        reproduced_bug_commands: Sequence[str],
        reproduced_bug_patch: str,
        selected_regression_tests: Sequence[str],
        recursion_limit: int = 150,
    ):
        config = {"recursion_limit": recursion_limit}

        input_state = {
            "issue_title": issue_title,
            "issue_body": issue_body,
            "issue_comments": issue_comments,
            "run_build": run_build,
            "run_regression_test": run_regression_test,
            "run_existing_test": run_existing_test,
            "reproduced_bug_file": reproduced_bug_file,
            "reproduced_bug_commands": reproduced_bug_commands,
            "reproduced_bug_patch": reproduced_bug_patch,
            "selected_regression_tests": selected_regression_tests,
            "max_refined_query_loop": 5,
        }

        output_state = self.subgraph.invoke(input_state, config)
        return {
            "edit_patch": output_state["edit_patch"],
            "reproducing_test_fail_log": output_state["reproducing_test_fail_log"],
            "exist_build": output_state.get("exist_build", False),
            "build_fail_log": output_state.get("build_fail_log", ""),
            "exist_test": output_state.get("exist_test", False),
            "existing_test_fail_log": output_state.get("existing_test_fail_log", ""),
        }
