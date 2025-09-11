import logging
import shutil
import tarfile
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Sequence

import docker
import pexpect

from prometheus.exceptions.docker_exception import DockerException
from prometheus.utils.logger_manager import get_thread_logger


class BaseContainer(ABC):
    """An abstract base class for managing Docker containers with file synchronization capabilities.

    This class provides core functionality for creating, managing, and interacting with Docker
    containers. It handles container lifecycle operations including building images, starting
    containers, updating files, and cleanup. The class is designed to be extended for specific
    container implementations that specifies the Dockerfile, how to build and how to run the test.

    Now supports persistent shell for maintaining command execution context.
    """

    client: docker.DockerClient = docker.from_env()
    tag_name: str
    workdir: str = "/app"
    container: docker.models.containers.Container
    project_path: Path
    timeout: int = 300  # Timeout for commands in seconds
    logger: logging.Logger
    shell: Optional[pexpect.spawn] = None  # Persistent shell

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
        self._logger, file_handler = get_thread_logger(__name__)
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
        self.shell = None

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
        Also initializes the persistent shell.
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

        # Initialize persistent shell
        self._start_persistent_shell()

    def _start_persistent_shell(self):
        """Start a persistent bash shell inside the container using pexpect."""
        if not self.container:
            self._logger.error("Container must be started before initializing shell")
            return

        self._logger.info("Starting persistent shell for interactive mode...")
        try:
            command = f"docker exec -it {self.container.id} /bin/bash"
            self.shell = pexpect.spawn(command, encoding="utf-8", timeout=self.timeout)

            # Wait for the initial shell prompt
            self.shell.expect([r"\$", r"#"], timeout=60)

            self._logger.info("Persistent shell is ready")
        except pexpect.exceptions.TIMEOUT:
            self._logger.error(
                "Timeout waiting for shell prompt. The container might be slow to start or misconfigured."
            )
            if self.shell:
                self.shell.close(force=True)
                self.shell = None
            raise DockerException("Timeout waiting for shell prompt.")
        except Exception as e:
            self._logger.error(f"Failed to start persistent shell: {e}")
            if self.shell:
                self.shell.close(force=True)
                self.shell = None
            raise DockerException(f"Failed to start persistent shell: {e}")

    def _restart_shell_if_needed(self):
        """Restart the shell if it's not alive."""
        if not self.shell or not self.shell.isalive():
            self._logger.warning("Shell not found or died. Attempting to restart...")
            if self.shell:
                self.shell.close(force=True)
            self._start_persistent_shell()

        if self.shell is None:
            raise DockerException("Failed to start or restart the persistent shell.")

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
        """Run build commands and return combined output."""
        if not self.build_commands:
            self._logger.error("No build commands defined")
            return ""

        command_output = ""
        for build_command in self.build_commands:
            command_output += f"$ {build_command}\n"
            command_output += f"{self.execute_command(build_command)}\n"
        return command_output

    def run_test(self) -> str:
        """Run test commands and return combined output."""
        if not self.test_commands:
            self._logger.error("No test commands defined")
            return ""

        command_output = ""
        for test_command in self.test_commands:
            command_output += f"$ {test_command}\n"
            command_output += f"{self.execute_command(test_command)}\n"
        return command_output

    def execute_command(self, command: str) -> str:
        """Execute a command in the running container using persistent shell.

        Args:
            command: Command to execute in the container.

        Returns:
            str: Output of the command.
        """
        self._logger.debug(f"Executing command: {command}")

        # Ensure shell is available
        self._restart_shell_if_needed()

        # Unique marker to identify command completion and exit code
        marker = "---CMD_DONE---"
        full_command = command.strip()
        marker_command = f"echo {marker}$?"

        try:
            self.shell.sendline(full_command)
            self.shell.sendline(marker_command)

            # Wait for the marker with exit code
            self.shell.expect(marker + r"(\d+)", timeout=self.timeout)
            exit_code = int(self.shell.match.group(1))

            # Get the output before the marker
            output_before_marker = self.shell.before

            # Clean up the output by removing command echoes
            all_lines = output_before_marker.splitlines()
            clean_lines = []
            for line in all_lines:
                stripped_line = line.strip()
                # Ignore the line if it's an echo of our commands
                if (
                    stripped_line != full_command
                    and marker_command not in stripped_line
                    and line not in ["\x1b[?2004l", "\x1b[?2004h"]
                ):
                    clean_lines.append(line)

            cleaned_output = "\n".join(clean_lines).strip()

            # Wait for the next shell prompt to ensure the shell is ready
            self.shell.expect([r"\$", r"#"], timeout=10)

            self._logger.debug(f"Command exit code: {exit_code}")
            self._logger.debug(f"Command output:\n{cleaned_output}")

            return cleaned_output

        except pexpect.exceptions.TIMEOUT:
            timeout_msg = f"""
*******************************************************************************
{command} timeout after {self.timeout} seconds
*******************************************************************************
"""
            self._logger.error(f"Command '{command}' timed out after {self.timeout} seconds")
            partial_output = getattr(self.shell, "before", "")
            return f"Command '{command}' timed out after {self.timeout} seconds. Partial output:\n{partial_output}{timeout_msg}"

        except Exception as e:
            raise DockerException(f"Error executing command '{command}': {e}")

    def reset_repository(self):
        """Reset the git repository in the container to a clean state."""
        self._logger.info("Resetting git repository in the container")
        self.execute_command("git reset --hard")
        self.execute_command("git clean -fd")

    def cleanup(self):
        """Clean up container resources and temporary files.

        Stops the persistent shell, stops and removes the container, removes the Docker image,
        and deletes temporary project files.
        """
        self._logger.info("Cleaning up container and temporary files")

        # Close persistent shell first
        if self.shell and self.shell.isalive():
            self._logger.info("Closing persistent shell...")
            self.shell.close(force=True)
            self.shell = None

        self._logger.info("Cleaning up container and temporary files")
        if self.container:
            self.container.stop(timeout=10)
            self.container.remove(force=True)
            self.container = None
            self.client.images.remove(self.tag_name, force=True)

        shutil.rmtree(self.project_path)
