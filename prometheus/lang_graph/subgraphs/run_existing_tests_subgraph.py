from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, StateGraph

from prometheus.docker.base_container import BaseContainer
from prometheus.git.git_repository import GitRepository
from prometheus.lang_graph.nodes.git_apply_patch_node import GitApplyPatchNode
from prometheus.lang_graph.nodes.run_existing_tests_node import RunExistingTestsNode
from prometheus.lang_graph.nodes.run_existing_tests_structure_node import (
    RunExistingTestsStructuredNode,
)
from prometheus.lang_graph.nodes.update_container_node import UpdateContainerNode
from prometheus.lang_graph.subgraphs.run_existing_tests_state import RunExistingTestsState


class RunExistingTestsSubgraph:
    """
    This class defines a LangGraph-based state machine that automatically runs existing tests
    for GitHub issues.
    """

    def __init__(
        self,
        base_model: BaseChatModel,
        container: BaseContainer,
        git_repo: GitRepository,
    ):
        """
        Initialize the run existing tests pipeline with all necessary parts.

        Args:
            base_model: Lighter LLM for simpler tasks (e.g., file selection).
            container: Docker-based sandbox for running code.
        """
        # Git apply patch node to apply the testing patch
        edit_patch_apply_node = GitApplyPatchNode(
            git_repo=git_repo, state_patch_name="testing_patch"
        )

        # Update the container with the current testing patch
        update_container_node = UpdateContainerNode(container=container, git_repo=git_repo)

        # Run existing tests node
        run_existing_tests_node = RunExistingTestsNode(container=container)

        # Get result node
        run_existing_tests_structured_node = RunExistingTestsStructuredNode(model=base_model)
        # Define the state machine
        workflow = StateGraph(RunExistingTestsState)

        workflow.add_node("edit_patch_apply_node", edit_patch_apply_node)
        workflow.add_node("update_container_node", update_container_node)
        workflow.add_node("run_existing_tests_node", run_existing_tests_node)

        workflow.add_node("run_existing_tests_structured_node", run_existing_tests_structured_node)
        workflow.set_entry_point("edit_patch_apply_node")
        workflow.add_edge("edit_patch_apply_node", "update_container_node")
        workflow.add_edge("update_container_node", "run_existing_tests_node")
        workflow.add_edge("run_existing_tests_node", "run_existing_tests_structured_node")
        workflow.add_edge("run_existing_tests_structured_node", END)

        # Compile the full LangGraph subgraph
        self.subgraph = workflow.compile()

    def invoke(
        self,
        testing_patch: str,
        recursion_limit: int = 50,
    ):
        """
        Run the bug existing subgraph.

        Args:
            testing_patch: The code patch to test.
            recursion_limit: Max steps before triggering recovery fallback.
        Returns:
            The result of the bug existing process
        """
        config = {"recursion_limit": recursion_limit}

        input_state = {
            "testing_patch": testing_patch,
            "success": False,
        }

        output_state = self.subgraph.invoke(input_state, config)
        return {
            "test_fail_log": output_state["test_fail_log"] if not output_state["success"] else "",
        }
