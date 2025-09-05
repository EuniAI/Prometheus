FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

# Install Docker CLI and other dependencies
RUN apt-get update && \
    apt-get install -y \
    git \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    build-essential \
    gcc \
    lsb-release && \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list && \
    apt-get update && \
    apt-get install -y docker-ce-cli && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

RUN pip install --upgrade pip \
    && pip install hatchling \
    && pip install .[test]

EXPOSE 9002

CMD ["uvicorn", "prometheus.app.main:app", "--host", "0.0.0.0", "--port", "9002"]