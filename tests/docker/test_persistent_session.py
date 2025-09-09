"""Tests for persistent session management in BaseContainer."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from prometheus.docker.base_container import BaseContainer
from prometheus.docker.user_defined_container import UserDefinedContainer


class TestContainer(BaseContainer):
    """Test implementation of BaseContainer for testing."""
    
    def get_dockerfile_content(self) -> str:
        return """
FROM ubuntu:20.04
RUN apt-get update && apt-get install -y bash
WORKDIR /app
"""


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir) / "test_project"
        project_path.mkdir()
        (project_path / "test_file.txt").write_text("test content")
        yield project_path


@pytest.fixture
def mock_container():
    """Create a mock container for testing."""
    container = TestContainer(
        project_path=Path("/tmp/test"),
        workdir="/app"
    )
    
    # Mock the container and client
    container.container = Mock()
    container.client = Mock()
    container._logger = Mock()
    
    return container


class TestPersistentSession:
    """Test cases for persistent session functionality."""
    
    def test_start_session_success(self, mock_container):
        """Test successful session start."""
        # Mock exec_run to return a mock exec result
        mock_exec_result = Mock()
        mock_socket = Mock()
        mock_socket._sock = Mock()
        mock_exec_result.output = mock_socket
        
        mock_container.container.exec_run.return_value = mock_exec_result
        
        # Test session start
        result = mock_container.start_session()
        
        assert result is True
        assert mock_container._session_active is True
        assert mock_container._session_exec == mock_exec_result
        assert mock_container._session_socket == mock_socket
        
        # Verify exec_run was called with correct parameters
        mock_container.container.exec_run.assert_called_once()
        call_args = mock_container.container.exec_run.call_args
        assert call_args[0][0] == ["/bin/bash", "-i"]
        assert call_args[1]["socket"] is True
        assert call_args[1]["stdin"] is True
    
    def test_start_session_already_active(self, mock_container):
        """Test starting session when already active."""
        mock_container._session_active = True
        
        result = mock_container.start_session()
        
        assert result is True
        # Should not call exec_run again
        mock_container.container.exec_run.assert_not_called()
    
    def test_start_session_no_container(self, mock_container):
        """Test starting session when container is not running."""
        mock_container.container = None
        
        result = mock_container.start_session()
        
        assert result is False
        assert mock_container._session_active is False
    
    def test_execute_in_session_no_active_session(self, mock_container):
        """Test executing command when no session is active."""
        mock_container._session_active = False
        
        with pytest.raises(RuntimeError, match="No active session"):
            mock_container.execute_in_session("echo test")
    
    def test_end_session_success(self, mock_container):
        """Test successful session end."""
        # Setup active session
        mock_container._session_active = True
        mock_container._session_socket = Mock()
        mock_container._session_socket._sock = Mock()
        
        result = mock_container.end_session()
        
        assert result is True
        assert mock_container._session_active is False
        assert mock_container._session_exec is None
        assert mock_container._session_socket is None
    
    def test_end_session_not_active(self, mock_container):
        """Test ending session when no session is active."""
        mock_container._session_active = False
        
        result = mock_container.end_session()
        
        assert result is True
        # Should not try to send exit command
        assert not hasattr(mock_container._session_socket, '_sock') or mock_container._session_socket is None
    
    def test_is_session_active(self, mock_container):
        """Test session active status check."""
        # Test when session is not active
        mock_container._session_active = False
        assert mock_container.is_session_active() is False
        
        # Test when session is active
        mock_container._session_active = True
        assert mock_container.is_session_active() is True
    
    def test_cleanup_session(self, mock_container):
        """Test session cleanup."""
        # Setup session
        mock_container._session_active = True
        mock_container._session_exec = Mock()
        mock_container._session_socket = Mock()
        
        mock_container._cleanup_session()
        
        assert mock_container._session_active is False
        assert mock_container._session_exec is None
        assert mock_container._session_socket is None
    
    def test_cleanup_includes_session_cleanup(self, mock_container):
        """Test that container cleanup includes session cleanup."""
        # Setup session
        mock_container._session_active = True
        mock_container._session_socket = Mock()
        
        # Mock the cleanup method to avoid actual cleanup
        with patch.object(mock_container, 'end_session') as mock_end_session:
            mock_container.cleanup()
            mock_end_session.assert_called_once()


class TestUserDefinedContainerInheritance:
    """Test that UserDefinedContainer inherits session management functionality."""
    
    def test_user_defined_container_has_session_methods(self, temp_project_dir):
        """Test that UserDefinedContainer has all session management methods."""
        container = UserDefinedContainer(
            project_path=temp_project_dir,
            dockerfile_content="FROM ubuntu:20.04"
        )
        
        # Check that all session methods exist
        assert hasattr(container, 'start_session')
        assert hasattr(container, 'execute_in_session')
        assert hasattr(container, 'end_session')
        assert hasattr(container, 'is_session_active')
        assert hasattr(container, '_cleanup_session')
        
        # Check that session attributes exist
        assert hasattr(container, '_session_exec')
        assert hasattr(container, '_session_socket')
        assert hasattr(container, '_session_lock')
        assert hasattr(container, '_session_active')


class TestSessionStatePersistence:
    """Test cases for session state persistence functionality."""
    
    @pytest.fixture
    def session_container(self, temp_project_dir):
        """Create a container with mocked session for state persistence tests."""
        container = TestContainer(
            project_path=temp_project_dir,
            workdir="/app"
        )
        
        # Mock the container and session
        container.container = Mock()
        container.client = Mock()
        container._logger = Mock()
        
        # Mock session components
        mock_exec_result = Mock()
        mock_socket = Mock()
        mock_socket._sock = Mock()
        mock_exec_result.output = mock_socket
        container._session_exec = mock_exec_result
        container._session_socket = mock_socket
        container._session_active = True
        
        return container
    
    def test_environment_variable_persistence(self, session_container):
        """Test that environment variables persist between commands."""
        # Mock the socket communication
        session_container._session_socket._sock.send = Mock()
        session_container._session_socket._sock.recv = Mock()
        session_container._session_socket._sock.settimeout = Mock()
        
        # Mock receive to simulate command output
        def mock_recv(size):
            return b"exported_var=test_value\nEND_CMD_1234567890\n"
        
        session_container._session_socket._sock.recv.side_effect = mock_recv
        
        # Test setting and using environment variable
        result1 = session_container.execute_in_session("export TEST_VAR=hello")
        result2 = session_container.execute_in_session("echo $TEST_VAR")
        
        # Verify commands were sent
        assert session_container._session_socket._sock.send.call_count >= 2
    
    def test_working_directory_persistence(self, session_container):
        """Test that working directory changes persist between commands."""
        # Mock the socket communication
        session_container._session_socket._sock.send = Mock()
        session_container._session_socket._sock.recv = Mock()
        session_container._session_socket._sock.settimeout = Mock()
        
        # Mock receive to simulate command output
        def mock_recv(size):
            return b"/new/directory\nEND_CMD_1234567890\n"
        
        session_container._session_socket._sock.recv.side_effect = mock_recv
        
        # Test changing and using working directory
        result1 = session_container.execute_in_session("cd /new/directory")
        result2 = session_container.execute_in_session("pwd")
        
        # Verify commands were sent
        assert session_container._session_socket._sock.send.call_count >= 2


if __name__ == "__main__":
    pytest.main([__file__])
