import shutil
import tempfile
from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest

from prometheus.docker.base_container import BaseContainer


class TestContainer(BaseContainer):
    """Concrete implementation of BaseContainer for testing."""

    def get_dockerfile_content(self) -> str:
        return "FROM python:3.9\nWORKDIR /app\nCOPY . /app/"


@pytest.fixture
def temp_project_dir():
    # Create a temporary directory with some test files
    temp_dir = Path(tempfile.mkdtemp())
    test_file = temp_dir / "test.txt"
    test_file.write_text("test content")

    yield temp_dir

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_docker_client():
    with patch.object(BaseContainer, "client", new_callable=Mock) as mock_client:
        yield mock_client


@pytest.fixture
def container(temp_project_dir, mock_docker_client):
    container = TestContainer(
        project_path=temp_project_dir,
        workdir="/app",
        build_commands=["pip install -r requirements.txt", "python setup.py build"],
        test_commands=["pytest tests/"],
    )
    container.tag_name = "test_container_tag"
    return container


def test_get_dockerfile_content(container):
    """Test that get_dockerfile_content returns expected content"""
    dockerfile_content = container.get_dockerfile_content()

    assert "FROM python:3.9" in dockerfile_content
    assert "WORKDIR /app" in dockerfile_content
    assert "COPY . /app/" in dockerfile_content


def test_build_docker_image(container, mock_docker_client):
    """Test building Docker image"""
    # Setup mock for api.build to return an iterable of log entries
    mock_build_logs = [
        {"stream": "Step 1/3 : FROM python:3.9"},
        {"stream": "Step 2/3 : WORKDIR /app"},
        {"stream": "Step 3/3 : COPY . /app/"},
        {"stream": "Successfully built abc123"},
    ]
    mock_docker_client.api.build.return_value = iter(mock_build_logs)

    # Execute
    container.build_docker_image()

    # Verify
    assert (container.project_path / "prometheus.Dockerfile").exists()
    mock_docker_client.api.build.assert_called_once_with(
        path=str(container.project_path),
        dockerfile="prometheus.Dockerfile",
        tag=container.tag_name,
        rm=True,
        decode=True,
    )


@patch("prometheus.docker.base_container.pexpect.spawn")
def test_start_container(mock_spawn, container, mock_docker_client):
    """Test starting Docker container"""
    # Setup mock for pexpect shell
    mock_shell = Mock()
    mock_spawn.return_value = mock_shell
    mock_shell.expect.return_value = 0  # Simulate successful prompt match

    # Setup mock for docker client
    mock_containers = Mock()
    mock_docker_client.containers = mock_containers
    mock_container = Mock()
    mock_container.id = "test_container_id"
    mock_containers.run.return_value = mock_container

    # Execute
    container.start_container()

    # Verify docker container run was called
    mock_containers.run.assert_called_once_with(
        container.tag_name,
        detach=True,
        tty=True,
        network_mode="host",
        environment={"PYTHONPATH": f"{container.workdir}:$PYTHONPATH"},
        volumes={"/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "rw"}},
    )

    # Verify pexpect shell was started
    mock_spawn.assert_called_once_with(
        f"docker exec -it {mock_container.id} /bin/bash",
        encoding="utf-8",
        timeout=container.timeout,
    )
    mock_shell.expect.assert_called()


def test_is_running(container):
    """Test is_running status check"""
    # Test when container is None
    assert not container.is_running()

    # Test when container exists
    container.container = Mock()
    assert container.is_running()


def test_update_files(container, temp_project_dir):
    """Test updating files in container"""
    # Setup
    container.container = Mock()
    container.execute_command = Mock()

    # Create test files
    test_file1 = temp_project_dir / "dir1" / "test1.txt"
    test_file2 = temp_project_dir / "dir2" / "test2.txt"
    test_file1.parent.mkdir(parents=True)
    test_file2.parent.mkdir(parents=True)
    test_file1.write_text("test1")
    test_file2.write_text("test2")

    updated_files = [Path("dir1/test1.txt"), Path("dir2/test2.txt")]
    removed_files = [Path("dir3/old.txt")]

    # Execute
    container.update_files(temp_project_dir, updated_files, removed_files)

    # Verify
    container.execute_command.assert_has_calls(
        [call("rm dir3/old.txt"), call("mkdir -p dir1"), call("mkdir -p dir2")]
    )
    assert container.container.put_archive.called


@patch("prometheus.docker.base_container.pexpect.spawn")
def test_execute_command(mock_spawn, container):
    """Test executing command in container using persistent shell"""
    # Setup mock shell
    mock_shell = Mock()
    mock_spawn.return_value = mock_shell

    # Setup container and shell
    container.container = Mock()
    container.container.id = "test_container_id"
    container.shell = mock_shell
    mock_shell.isalive.return_value = True

    # Mock the shell interactions
    mock_shell.match = Mock()
    mock_shell.match.group.return_value = "0"  # Exit code 0
    mock_shell.before = "test command\ncommand output"

    # Execute
    result = container.execute_command("test command")

    # Verify shell interactions
    assert mock_shell.sendline.call_count == 2  # Command + marker command
    mock_shell.expect.assert_called()

    # The result should contain the cleaned output
    assert "command output" in result


def test_execute_command_with_mock(container):
    """Test executing command with direct mocking"""
    # Setup - directly mock the execute_command method
    container.execute_command = Mock(return_value="mocked output")
    container.container = Mock()

    # Execute
    result = container.execute_command("test command")

    # Verify
    container.execute_command.assert_called_once_with("test command")
    assert result == "mocked output"


def test_reset_repository(container):
    """Test container reset repository"""
    # Setup - Mock the execute_command method
    container.execute_command = Mock(return_value="Command output")
    container.container = Mock()

    # Execute
    container.reset_repository()

    # Verify - Check that execute_command was called twice with the correct commands
    assert container.execute_command.call_count == 2
    expected_calls = [call("git reset --hard"), call("git clean -fd")]
    container.execute_command.assert_has_calls(expected_calls, any_order=False)


@patch("prometheus.docker.base_container.pexpect.spawn")
def test_cleanup(mock_spawn, container, mock_docker_client):
    """Test cleanup of container resources"""
    # Setup
    mock_container = Mock()
    container.container = mock_container

    # Setup mock shell
    mock_shell = Mock()
    mock_shell.isalive.return_value = True
    container.shell = mock_shell

    # Execute
    container.cleanup()

    # Verify shell cleanup
    mock_shell.close.assert_called_once_with(force=True)

    # Verify container cleanup
    mock_container.stop.assert_called_once_with(timeout=10)
    mock_container.remove.assert_called_once_with(force=True)
    mock_docker_client.images.remove.assert_called_once_with(container.tag_name, force=True)
    assert not container.project_path.exists()


def test_run_build(container):
    """Test that build commands are executed correctly"""
    container.execute_command = Mock()
    container.execute_command.side_effect = ["Output 1", "Output 2"]

    build_output = container.run_build()

    # Verify execute_command was called for each build command
    assert container.execute_command.call_count == 2
    container.execute_command.assert_any_call("pip install -r requirements.txt")
    container.execute_command.assert_any_call("python setup.py build")

    # Verify output format
    expected_output = (
        "$ pip install -r requirements.txt\nOutput 1\n$ python setup.py build\nOutput 2\n"
    )
    assert build_output == expected_output


def test_run_test(container):
    """Test that test commands are executed correctly"""
    container.execute_command = Mock()
    container.execute_command.return_value = "Test passed"

    test_output = container.run_test()

    # Verify execute_command was called for the test command
    container.execute_command.assert_called_once_with("pytest tests/")

    # Verify output format
    expected_output = "$ pytest tests/\nTest passed\n"
    assert test_output == expected_output


def test_run_build_no_commands(container):
    """Test run_build when no build commands are defined"""
    container.build_commands = None
    result = container.run_build()
    assert result == ""


def test_run_test_no_commands(container):
    """Test run_test when no test commands are defined"""
    container.test_commands = None
    result = container.run_test()
    assert result == ""


@patch("prometheus.docker.base_container.pexpect.spawn")
def test_restart_shell_if_needed(mock_spawn, container):
    """Test shell restart functionality"""
    # Setup
    mock_shell_dead = Mock()
    mock_shell_dead.isalive.return_value = False

    mock_shell_new = Mock()
    mock_shell_new.expect.return_value = 0
    mock_spawn.return_value = mock_shell_new

    container.container = Mock()
    container.container.id = "test_container_id"
    container.shell = mock_shell_dead

    # Execute
    container._restart_shell_if_needed()

    # Verify old shell was closed and new one started
    mock_shell_dead.close.assert_called_once_with(force=True)
    mock_spawn.assert_called_once()
    assert container.shell == mock_shell_new
