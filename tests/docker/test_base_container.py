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

    def run_build(self):
        """Simple implementation for testing"""
        return self.execute_command("echo 'Building...'")

    def run_test(self):
        """Simple implementation for testing"""
        return self.execute_command("echo 'Testing...'")


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
    container = TestContainer(temp_project_dir)
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
    # Execute
    container.build_docker_image()

    # Verify
    assert (container.project_path / "prometheus.Dockerfile").exists()
    mock_docker_client.images.build.assert_called_once_with(
        path=str(container.project_path), dockerfile="prometheus.Dockerfile", tag=container.tag_name
    )


def test_start_container(container, mock_docker_client):
    """Test starting Docker container"""
    # Setup mock
    mock_containers = Mock()
    mock_docker_client.containers = mock_containers

    # Execute
    container.start_container()

    # Verify
    mock_containers.run.assert_called_once_with(
        container.tag_name,
        detach=True,
        tty=True,
        network_mode="host",
        environment={"PYTHONPATH": f"{container.workdir}:$PYTHONPATH"},
        volumes={"/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "rw"}},
    )


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
    mock_execute = Mock()
    container.execute_command = mock_execute

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
    mock_execute.assert_has_calls(
        [call("rm dir3/old.txt"), call("mkdir -p dir1"), call("mkdir -p dir2")]
    )
    assert container.container.put_archive.called


def test_execute_command(container):
    """Test executing command in container"""
    # Setup
    mock_container = Mock()
    mock_exec_result = Mock()
    mock_exec_result.exit_code = 0
    mock_exec_result.output = b"command output"
    mock_container.exec_run.return_value = mock_exec_result
    container.container = mock_container

    # Execute
    result = container.execute_command("test command")

    # Verify
    mock_container.exec_run.assert_called_once_with(
        "timeout -k 5 120s /bin/bash -lc test command", workdir=container.workdir
    )
    assert result == "command output"


def test_restart_container(container):
    """Test container restart"""
    # Setup
    mock_container = Mock()
    container.container = mock_container
    container.start_container = Mock()

    # Execute
    container.restart_container()

    # Verify
    mock_container.stop.assert_called_once_with(timeout=10)
    mock_container.remove.assert_called_once_with(force=True)
    container.start_container.assert_called_once()


def test_cleanup(container, mock_docker_client):
    """Test cleanup of container resources"""
    # Setup
    mock_container = Mock()
    container.container = mock_container

    # Execute
    container.cleanup()

    # Verify
    mock_container.stop.assert_called_once_with(timeout=10)
    mock_container.remove.assert_called_once_with(force=True)
    mock_docker_client.images.remove.assert_called_once_with(container.tag_name, force=True)
    assert not container.project_path.exists()
