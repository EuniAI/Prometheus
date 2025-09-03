import uuid
from pathlib import Path
from typing import Optional, Sequence

from prometheus.docker.base_container import BaseContainer


class GeneralContainer(BaseContainer):
    """A general-purpose container with a comprehensive development environment.

    This container provides a full Ubuntu-based development environment with common
    development tools and languages pre-installed, including Python, Node.js, Java,
    and various build tools. It's designed to be a flexible container that can
    handle various types of projects through direct command execution rather than
    predefined build and test methods.

    The container includes:
        - Build tools (gcc, g++, cmake, make)
        - Programming languages (Python 3, Node.js, Java)
        - Development tools (git, gdb)
        - Database clients (PostgreSQL, MySQL, SQLite)
        - Text editors (vim, nano)
        - Docker CLI for container management
        - Various utility tools (curl, wget, zip, etc.)

    Unlike specialized containers, this container does not implement run_build() or
    run_test() methods. Instead, the agent will use execute_command() directly for
    custom build and test operations.
    """

    def __init__(
        self,
        project_path: Path,
        build_commands: Optional[Sequence[str]] = None,
        test_commands: Optional[Sequence[str]] = None,
    ):
        """Initialize the general container with a unique tag name.

        Args:
            project_path (Path): Path to the project directory to be containerized.
        """
        super().__init__(
            project_path=project_path, build_commands=build_commands, test_commands=test_commands
        )
        self.tag_name = f"prometheus_general_container_{uuid.uuid4().hex[:10]}"

    def get_dockerfile_content(self) -> str:
        """Get the Dockerfile content for the general-purpose container.

        The Dockerfile sets up an Ubuntu-based environment with a comprehensive
        set of development tools and languages installed. It includes Python,
        Node.js, Java, and various build tools, making it suitable for different
        types of projects.

        Returns:
            str: Content of the Dockerfile as a string.
        """
        DOCKERFILE_CONTENT = """\
FROM ubuntu:24.04

# Avoid timezone prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Set working directory
WORKDIR /app

# Install essential build and development tools
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    curl \
    wget \
    python3 \
    python3-pip \
    python3-dev \
    python3-venv \
    nodejs \
    npm \
    default-jdk \
    gcc \
    g++ \
    gdb \
    postgresql-client \
    mysql-client \
    sqlite3 \
    iputils-ping \
    vim \
    nano \
    zip \
    unzip \
    ca-certificates \
    gnupg \
    lsb-release

RUN mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

RUN apt-get update && apt-get install -y docker-ce-cli

RUN apt-get clean
RUN rm -rf /var/lib/apt/lists/*
RUN ln -s /usr/bin/python3 /usr/bin/python

# Copy project files
COPY . /app/
"""
        return DOCKERFILE_CONTENT
