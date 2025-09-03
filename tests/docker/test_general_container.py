import shutil
import tempfile
from pathlib import Path

import pytest

from prometheus.docker.general_container import GeneralContainer


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
def container(temp_project_dir):
    return GeneralContainer(temp_project_dir)


def test_initialization(container, temp_project_dir):
    """Test that the container is initialized correctly"""
    assert isinstance(container.tag_name, str)
    assert container.tag_name.startswith("prometheus_general_container_")
    assert container.project_path != temp_project_dir
    assert (container.project_path / "test.txt").exists()


def test_get_dockerfile_content(container):
    dockerfile_content = container.get_dockerfile_content()

    assert dockerfile_content

    assert "FROM ubuntu:24.04" in dockerfile_content
    assert "WORKDIR /app" in dockerfile_content
    assert "RUN apt-get update" in dockerfile_content
    assert "COPY . /app/" in dockerfile_content
