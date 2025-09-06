import logging
import shutil
import tarfile
import tempfile
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Sequence

import docker


class BaseContainer(ABC):
    """An abstract base class for managing Docker containers with file synchronization capabilities.

    This class provides core functionality for creating, managing, and interacting with Docker
    containers. It handles container lifecycle operations including building images, starting
    containers, updating files, and cleanup. The class is designed to be extended for specific
    container implementations that specifies the Dockerfile, how to build and how to run the test.
    """

    client: docker.DockerClient = docker.from_env()
    tag_name: str
    workdir: str = "/app"
    container: docker.models.containers.Container
    project_path: Path
    timeout: int = 300  # Timeout for commands in seconds
    logger: logging.Logger

    def __init__(
        self,
        project_path: Path,
        workdir: Optional[str] = None,
        build_commands: Optional[Sequence[str]] = None,
        test_commands: Optional[Sequence[str]] = None,
    ):
        """Initialize the container with a project directory.

        Creates a temporary copy of the project directory to work with.

        Args:
          project_path: Path to the project directory to be containerized.
        """
        self._logger = logging.getLogger(
            f"thread-{threading.get_ident()}.{self.__class__.__module__}.{self.__class__.__name__}"
        )
        temp_dir = Path(tempfile.mkdtemp())
        temp_project_path = temp_dir / project_path.name
        shutil.copytree(project_path, temp_project_path)
        self.project_path = temp_project_path.absolute()
        self._logger.info(f"Created temporary project directory: {self.project_path}")
        self.build_commands = build_commands
        self.test_commands = test_commands

        if workdir:
            self.workdir = workdir
        self._logger.debug(f"Using workdir: {self.workdir}")

        self.container = None
        self._session_id = None  # ID of the active session
        self._session_active = False  # Whether a session is currently active

    @abstractmethod
    def get_dockerfile_content(self) -> str:
        """Get the content of the Dockerfile for building the container image.

        Returns:
            str: Content of the Dockerfile as a string.
        """
        pass

    def build_docker_image(self):
        """Build a Docker image using the Dockerfile content.

        Creates a Dockerfile in the project directory and builds a Docker image
        using the specified tag name.
        """
        dockerfile_content = self.get_dockerfile_content()
        dockerfile_path = self.project_path / "prometheus.Dockerfile"
        dockerfile_path.write_text(dockerfile_content)

        # Temporary move .dockerignore file
        dockerignore_path = self.project_path / ".dockerignore"
        backup_path = None

        if dockerignore_path.exists():
            backup_path = self.project_path / ".dockerignore.backup"
            dockerignore_path.rename(backup_path)
            self._logger.info("Temporarily renamed .dockerignore to avoid excluding files")

        # Log the build process
        self._logger.info(f"Building docker image {self.tag_name}")

        # Build the Docker image
        try:
            self.client.images.build(
                path=str(self.project_path), dockerfile=dockerfile_path.name, tag=self.tag_name
            )
        finally:
            # Restore .dockerignore
            if backup_path and backup_path.exists():
                backup_path.rename(dockerignore_path)
                self._logger.info("Restored .dockerignore file")

    def start_container(self):
        """Start a Docker container from the built image.

        Starts a detached container with TTY enabled and mounts the Docker socket.
        """
        self._logger.info(f"Starting container from image {self.tag_name}")
        self.container = self.client.containers.run(
            self.tag_name,
            detach=True,
            tty=True,
            network_mode="host",
            environment={"PYTHONPATH": f"{self.workdir}:$PYTHONPATH"},
            volumes={"/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "rw"}},
        )

    def is_running(self) -> bool:
        return bool(self.container)

    def update_files(
        self, project_root_path: Path, updated_files: Sequence[Path], removed_files: Sequence[Path]
    ):
        """Update files in the running container with files from a local directory.

        Creates a tar archive of the new files and copies them into the workdir of the container.

        Args:
            project_root_path: Path to the project root directory.
            updated_files: List of file paths (relative to project_root_path) to update in the container.
            removed_files: List of file paths (relative to project_root_path) to remove from the container.
        """
        if not project_root_path.is_absolute():
            raise ValueError("project_root_path {project_root_path} must be a absolute path")

        self._logger.info("Updating files in the container after edits.")
        for file in removed_files:
            self._logger.info(f"Removing file {file} in the container")
            self.execute_command(f"rm {file}")

        parent_dirs = {str(file.parent) for file in updated_files}
        for dir_path in sorted(parent_dirs):
            self._logger.info(f"Creating directory {dir_path} in the container")
            self.execute_command(f"mkdir -p {dir_path}")

        with tempfile.NamedTemporaryFile() as temp_tar:
            with tarfile.open(fileobj=temp_tar, mode="w") as tar:
                for file in updated_files:
                    local_absolute_file = project_root_path / file
                    self._logger.info(f"Updating {file} in the container")
                    tar.add(local_absolute_file, arcname=str(file))

            temp_tar.seek(0)

            self.container.put_archive(self.workdir, temp_tar.read())

        self._logger.info("Files updated successfully")

    def run_build(self) -> str:
        if not self.build_commands:
            self._logger.error("No build commands defined")
            return ""

        command_output = ""
        for build_command in self.build_commands:
            command_output += f"$ {build_command}\n"
            command_output += f"{self.execute_command(build_command)}\n"
        return command_output

    def run_test(self) -> str:
        if not self.test_commands:
            self._logger.error("No test commands defined")
            return ""

        command_output = ""
        for test_command in self.test_commands:
            command_output += f"$ {test_command}\n"
            command_output += f"{self.execute_command(test_command)}\n"
        return command_output

    def execute_command(self, command: str) -> str:
        """Execute a command in the running container.

        Args:
            command: Command to execute in the container.

        Returns:
            str: Output of the command as a string.
        """
        # Use session-based execution if a session is active
        if self._session_active:
            return self.execute_in_session(command)
        
        timeout_msg = f"""
*******************************************************************************
{command} timeout after {self.timeout} seconds
*******************************************************************************
"""
        bash_cmd = ["/bin/bash", "-lc", command]
        full_cmd = ["timeout", "-k", "5", f"{self.timeout}s", *bash_cmd]
        self._logger.debug(f"Running command in container: {command}")
        exec_result = self.container.exec_run(full_cmd, workdir=self.workdir)
        exec_result_str = exec_result.output.decode("utf-8")

        if exec_result.exit_code in (124, 137):
            exec_result_str += timeout_msg

        self._logger.debug(f"Command output:\n{exec_result_str}")
        return exec_result_str

    def reset_repository(self):
        """Reset the git repository in the container to a clean state."""
        self._logger.info("Resetting git repository in the container")
        self.execute_command("git reset --hard")
        self.execute_command("git clean -fd")

    def start_session(self):
        """Start a persistent interactive session.
        
        Creates a persistent bash session that maintains state between command executions.
        This allows environment variables, working directory, and other session state
        to persist across multiple execute_command calls.
        
        Note: This implementation uses a state file approach to maintain environment
        variables and working directory between command executions.
        """
        if self._session_active:
            self._logger.warning("Session already active, ending previous session")
            self.end_session()
        
        self._logger.info("Starting persistent interactive session")
        
        # Initialize session state by creating a state file
        self.execute_command("mkdir -p /tmp/prometheus_session")
        self.execute_command("touch /tmp/prometheus_session/env_state")
        self.execute_command("pwd > /tmp/prometheus_session/cwd_state")
        
        self._session_active = True
        self._logger.debug("Session started with state tracking")

    def execute_in_session(self, command: str) -> str:
        """Execute a command in the persistent session.
        
        Args:
            command: Command to execute in the active session.
            
        Returns:
            str: Output of the command as a string.
        """
        if not self._session_active:
            self._logger.warning("No active session, starting new session")
            self.start_session()
        
        self._logger.debug(f"Executing in session: {command}")
        
        # For session-based execution, we load the session state first
        # then execute the command, and finally save the new state
        
        # Load environment and working directory from previous session
        env_load_cmd = "if [ -f /tmp/prometheus_session/env_state ]; then source /tmp/prometheus_session/env_state; fi"
        cwd_load_cmd = "if [ -f /tmp/prometheus_session/cwd_state ]; then cd $(cat /tmp/prometheus_session/cwd_state); fi"
        
        # Execute the command with session state
        full_command = f"{env_load_cmd} && {cwd_load_cmd} && {command}"
        
        timeout_msg = f"""
*******************************************************************************
{command} timeout after {self.timeout} seconds
*******************************************************************************
"""
        bash_cmd = ["/bin/bash", "-lc", full_command]
        full_cmd = ["timeout", "-k", "5", f"{self.timeout}s", *bash_cmd]
        
        exec_result = self.container.exec_run(full_cmd, workdir=self.workdir)
        exec_result_str = exec_result.output.decode("utf-8")

        if exec_result.exit_code in (124, 137):
            exec_result_str += timeout_msg

        # Save environment state for next command
        self._save_session_state()
        
        self._logger.debug(f"Session command output:\n{exec_result_str}")
        return exec_result_str

    def _save_session_state(self):
        """Save the current session state (environment and working directory)."""
        # Save current environment variables (excluding special shell variables)
        env_save_cmd = "env | grep -vE '^(PWD|OLDPWD|SHLVL|_|\\(|\\))' > /tmp/prometheus_session/env_state"
        # Save current working directory
        cwd_save_cmd = "pwd > /tmp/prometheus_session/cwd_state"
        
        # Execute state saving commands
        self.container.exec_run(["/bin/bash", "-lc", env_save_cmd], workdir=self.workdir)
        self.container.exec_run(["/bin/bash", "-lc", cwd_save_cmd], workdir=self.workdir)

    def end_session(self):
        """Clean up the persistent session."""
        if self._session_active:
            self._logger.info("Ending persistent session")
            # Clean up any session-related resources
            self._session_id = None
            self._session_active = False
            self._logger.debug("Session ended")
        else:
            self._logger.debug("No active session to end")

    def cleanup(self):
        """Clean up container resources and temporary files.

        Stops and removes the container, removes the Docker image,
        and deletes temporary project files.
        """
        self._logger.info("Cleaning up container and temporary files")
        
        # End any active session to prevent resource leaks
        self.end_session()
        
        if self.container:
            self.container.stop(timeout=10)
            self.container.remove(force=True)
            self.container = None
            self.client.images.remove(self.tag_name, force=True)

        shutil.rmtree(self.project_path)
