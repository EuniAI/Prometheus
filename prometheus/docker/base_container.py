import logging
import shutil
import tarfile
import tempfile
import threading
import time
import socket
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Sequence

import docker

from prometheus.utils.logger_manager import get_thread_logger


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
    
    # Session management attributes
    _session_exec: Optional[docker.models.containers.ExecResult] = None
    _session_socket = None
    _session_lock: threading.Lock = threading.Lock()
    _session_active: bool = False

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

    def start_session(self) -> bool:
        """Start a persistent interactive session in the container.
        
        This creates a long-running bash session that maintains state between commands,
        including environment variables, working directory, and shell variables.
        
        Returns:
            bool: True if session started successfully, False otherwise.
        """
        with self._session_lock:
            if self._session_active:
                self._logger.warning("Session is already active")
                return True
                
            if not self.container:
                self._logger.error("Container is not running")
                return False
                
            try:
                # Create a non-interactive bash session with controlled environment
                # This reduces ANSI escape sequences and command echo interference
                self._session_exec = self.container.exec_run(
                    ["/bin/bash", "--norc", "--noprofile"],
                    socket=True,
                    stdin=True,
                    stdout=True,
                    stderr=True,
                    workdir=self.workdir,
                    environment={
                        "PYTHONPATH": f"{self.workdir}:$PYTHONPATH",
                        "PS1": "",  # Remove prompt to avoid interference
                        "TERM": "dumb",  # Disable terminal features
                        "PAGER": "cat",  # Disable pagers
                    }
                )
                
                # Get the socket for communication
                self._session_socket = self._session_exec.output
                
                # Wait a moment for bash to initialize
                time.sleep(0.5)
                
                # Send initial setup commands to ensure clean environment
                self._send_to_session("set +H\n")  # Disable history expansion
                self._send_to_session("set +o emacs\n")  # Disable emacs mode
                self._send_to_session("set +o vi\n")  # Disable vi mode
                self._send_to_session("unset HISTFILE\n")  # Disable history file
                self._send_to_session("export PS1=''\n")  # Ensure no prompt
                self._send_to_session("cd " + self.workdir + "\n")
                
                # Clear any initialization output
                time.sleep(0.2)
                self._receive_from_session(timeout=0.1)
                
                self._session_active = True
                self._logger.info("Persistent session started successfully")
                return True
                
            except Exception as e:
                self._logger.error(f"Failed to start session: {e}")
                self._cleanup_session()
                return False

    def _send_to_session(self, command: str) -> None:
        """Send a command to the persistent session.
        
        Args:
            command: Command to send to the session.
        """
        if not self._session_socket:
            raise RuntimeError("No active session")
            
        try:
            self._session_socket._sock.send(command.encode('utf-8'))
        except Exception as e:
            self._logger.error(f"Failed to send command to session: {e}")
            raise

    def _receive_from_session(self, timeout: float = 1.0) -> str:
        """Receive output from the persistent session.
        
        Args:
            timeout: Timeout in seconds for receiving data.
            
        Returns:
            str: Output received from the session.
        """
        if not self._session_socket:
            raise RuntimeError("No active session")
            
        try:
            # Set socket timeout
            self._session_socket._sock.settimeout(timeout)
            
            # Receive data
            data = self._session_socket._sock.recv(4096)
            return data.decode('utf-8', errors='ignore')
            
        except socket.timeout:
            return ""
        except Exception as e:
            self._logger.error(f"Failed to receive from session: {e}")
            raise

    def _clean_command_output(self, output: str) -> str:
        """Clean command output by removing artifacts and escape sequences.
        
        Args:
            output: Raw command output to clean.
            
        Returns:
            str: Cleaned output with artifacts removed.
        """
        import re
        
        # Remove ANSI escape sequences
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        output = ansi_escape.sub('', output)
        
        # Remove any stray command markers
        marker_pattern = re.compile(r'[=]*(?:START|END)_CMD_\d+[=]*')
        output = marker_pattern.sub('', output)
        
        # Remove carriage returns and normalize line endings
        output = output.replace('\r\n', '\n').replace('\r', '\n')
        
        # Remove empty lines at the beginning and end
        lines = output.split('\n')
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
            
        return '\n'.join(lines)

    def execute_in_session(self, command: str) -> str:
        """Execute a command in the persistent session.
        
        This method executes commands in the persistent bash session, maintaining
        state between calls including environment variables, working directory,
        and shell variables.
        
        Args:
            command: Command to execute in the persistent session.
            
        Returns:
            str: Output of the command as a string.
            
        Raises:
            RuntimeError: If no active session exists.
        """
        if not self._session_active:
            raise RuntimeError("No active session. Call start_session() first.")
            
        with self._session_lock:
            try:
                # Clear any pending output
                self._receive_from_session(timeout=0.1)
                
                # Send the command with unique markers and controlled output
                command_id = f"CMD_{int(time.time() * 1000)}"
                # Use printf instead of echo to avoid shell interpretation issues
                # Add newlines to ensure proper separation
                full_command = f"printf '\\n==START_{command_id}==\\n'; {command}; printf '\\n==END_{command_id}==\\n'\n"
                
                self._send_to_session(full_command)
                
                # Collect output until we see the end marker
                output_lines = []
                start_found = False
                timeout_count = 0
                max_timeouts = self.timeout * 2  # Allow for timeout seconds worth of 0.5s intervals
                
                while timeout_count < max_timeouts:
                    try:
                        data = self._receive_from_session(timeout=0.5)
                        if not data:
                            timeout_count += 1
                            continue
                            
                        # Accumulate all received data
                        all_data = data
                        
                        # Continue receiving until we have enough data or timeout
                        additional_timeouts = 0
                        while additional_timeouts < 3:  # Wait up to 1.5 seconds more
                            try:
                                more_data = self._receive_from_session(timeout=0.5)
                                if more_data:
                                    all_data += more_data
                                    additional_timeouts = 0
                                else:
                                    additional_timeouts += 1
                            except socket.timeout:
                                additional_timeouts += 1
                        
                        # Process accumulated data
                        lines = all_data.split('\n')
                        start_marker = f'==START_{command_id}=='
                        end_marker = f'==END_{command_id}=='
                        
                        for i, line in enumerate(lines):
                            if start_marker in line:
                                start_found = True
                                # Look for end marker
                                for j in range(i + 1, len(lines)):
                                    if end_marker in lines[j]:
                                        # Extract output between markers
                                        command_output = lines[i + 1:j]
                                        result = '\n'.join(command_output).strip()
                                        # Clean up any remaining artifacts
                                        result = self._clean_command_output(result)
                                        self._logger.debug(f"Session command output:\n{result}")
                                        return result
                                
                        # Check if we found start marker but no end marker
                        if start_found:
                            # Collect all content after start marker
                            for i, line in enumerate(lines):
                                if start_marker in line:
                                    remaining_output = lines[i + 1:]
                                    output_lines.extend(remaining_output)
                                    break
                                    
                        timeout_count = 0  # Reset timeout counter if we got data
                        
                    except socket.timeout:
                        timeout_count += 1
                        continue
                        
                # If we get here, we timed out
                timeout_msg = f"""
*******************************************************************************
{command} timeout after {self.timeout} seconds in persistent session
*******************************************************************************
"""
                self._logger.warning(f"Command timed out in session: {command}")
                return '\n'.join(output_lines).strip() + timeout_msg
                
            except Exception as e:
                self._logger.error(f"Error executing command in session: {e}")
                # Try to recover the session
                self._cleanup_session()
                raise RuntimeError(f"Session error: {e}")

    def is_session_active(self) -> bool:
        """Check if a persistent session is currently active.
        
        Returns:
            bool: True if session is active, False otherwise.
        """
        return self._session_active

    def _cleanup_session(self) -> None:
        """Clean up session resources."""
        try:
            if self._session_socket:
                self._session_socket.close()
        except Exception as e:
            self._logger.debug(f"Error closing session socket: {e}")
        finally:
            self._session_exec = None
            self._session_socket = None
            self._session_active = False

    def end_session(self) -> bool:
        """End the persistent session and clean up resources.
        
        This method properly closes the persistent bash session and cleans up
        all associated resources.
        
        Returns:
            bool: True if session ended successfully, False otherwise.
        """
        with self._session_lock:
            if not self._session_active:
                self._logger.warning("No active session to end")
                return True
                
            try:
                # Send exit command to bash
                if self._session_socket:
                    self._send_to_session("exit\n")
                    time.sleep(0.2)  # Give bash time to exit
                    
                self._cleanup_session()
                self._logger.info("Persistent session ended successfully")
                return True
                
            except Exception as e:
                self._logger.error(f"Error ending session: {e}")
                self._cleanup_session()  # Force cleanup even if there was an error
                return False

    def reset_repository(self):
        """Reset the git repository in the container to a clean state."""
        self._logger.info("Resetting git repository in the container")
        self.execute_command("git reset --hard")
        self.execute_command("git clean -fd")

    def cleanup(self):
        """Clean up container resources and temporary files.

        Stops and removes the container, removes the Docker image,
        and deletes temporary project files.
        """
        self._logger.info("Cleaning up container and temporary files")
        
        # Clean up session first
        if self._session_active:
            self.end_session()
            
        if self.container:
            self.container.stop(timeout=10)
            self.container.remove(force=True)
            self.container = None
            self.client.images.remove(self.tag_name, force=True)

        shutil.rmtree(self.project_path)
