# GitHub Issue Auto Debug Script Usage Guide

## Overview

`prometheus/script/github_issue_debug.py` is an automated script for:
1. Retrieving detailed information (title, body, comments, etc.) of a specified issue from the GitHub API.
2. Automatically uploading the GitHub repository to Prometheus.
3. Using Prometheus's AI analysis capabilities to debug the issue.
4. Returning analysis results, fix patches, etc.

## Prerequisites

### 1. Start Prometheus Service
Ensure the Prometheus service is running:
```bash
# Start using docker-compose
docker-compose up --build
```

### 2. Obtain GitHub Personal Access Token
1. Visit https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select the appropriate permission scope:
   - `repo` (access private repositories)
   - `public_repo` (access public repositories)
4. Generate and save the token.

## Basic Usage

### Simple Example
```bash
python github_issue_debug.py \
    --github-token "your_token_here" \
    --repo "owner/repository" \
    --issue-number 42
```

### Full Parameter Example
```bash
python github_issue_debug.py \
    --github-token "ghp_xxxxxxxxxxxxxxxxxxxx" \
    --repo "microsoft/vscode" \
    --issue-number 123 \
    --prometheus-url "http://localhost:9002/v1.2" \
    --output-file "debug_result.json" \
    --run-build \
    --run-test \
    --run-reproduction-test \
    --run-regression-test \
    --push-to-remote \
    --image-name "python:3.11-slim" \
    --workdir "/app" \
    --build-commands "pip install -r requirements.txt" "python setup.py build" \
    --test-commands "pytest tests/" \
    --candidate-patches 3
```

## Parameter Details

### Required Parameters
- `--github-token`: GitHub Personal Access Token
- `--repo`: GitHub repository name in the format `owner/repo`
- `--issue-number`: Issue number to process

### Optional Parameters
- `--prometheus-url`: Prometheus service address (default: http://localhost:8000)
- `--output-file`: Path to the result output file (if not specified, output to console)

### Validation Options
- `--run-build`: Run build validation for the generated patch
- `--run-test`: Run test validation for the generated patch
- `--run-reproduction-test`: Run reproduction test to verify if the issue can be reproduced
- `--run-regression-test`: Run regression test to ensure existing functionality is not broken
- `--push-to-remote`: Push the fix to a remote Git branch

### Docker Environment Configuration
- `--dockerfile-content`: Specify Dockerfile content directly
- `--image-name`: Use a predefined Docker image
- `--workdir`: Working directory inside the container (default: /app)
- `--build-commands`: List of build commands
- `--test-commands`: List of test commands

### Other Options
- `--candidate-patches`: Number of candidate patches (default: 6)

## Usage Scenarios

### Scenario 1: Simple Bug Report Analysis
```bash
# Analyze a simple bug report without running any validation
python github_issue_debug.py \
    --github-token "your_token" \
    --repo "pytorch/pytorch" \
    --issue-number 89123
```

### Scenario 2: Python Project with Test Validation
```bash
# Perform a complete debug for a Python project, including build and test validation
python github_issue_debug.py \
    --github-token "your_token" \
    --repo "requests/requests" \
    --issue-number 5678 \
    --run-build \
    --run-test \
    --run-reproduction-test \
    --run-regression-test \
    --image-name "python:3.11-slim" \
    --build-commands "pip install -e ." \
    --test-commands "pytest tests/test_requests.py"
```

### Scenario 3: Node.js Project with Auto Push
```bash
# Process an issue for a Node.js project and automatically push the fix to a remote branch
python github_issue_debug.py \
    --github-token "your_token" \
    --repo "facebook/react" \
    --issue-number 9876 \
    --run-build \
    --run-test \
    --run-reproduction-test \
    --run-regression-test \
    --push-to-remote \
    --image-name "node:18-slim" \
    --build-commands "npm ci" "npm run build" \
    --test-commands "npm test"
```

### Scenario 4: Custom Docker Environment
```bash
# Use a custom Dockerfile for debugging
python github_issue_debug.py \
    --github-token "your_token" \
    --repo "tensorflow/tensorflow" \
    --issue-number 4321 \
    --run-build \
    --dockerfile-content "FROM tensorflow/tensorflow:latest-gpu
WORKDIR /app
COPY . /app
RUN pip install -r requirements.txt" \
    --workdir "/app" \
    --build-commands "python setup.py build_ext --inplace" \
    --test-commands "python -m pytest tests/unit/"
```

## Output Result Explanation

After execution, the script outputs results in JSON format, including the following fields:

```json
{
  "success": true,
  "issue_info": {
    "repo": "owner/repo",
    "number": 123,
    "title": "Issue Title",
    "url": "https://github.com/owner/repo/issues/123",
    "state": "open"
  },
  "prometheus_result": {
    "patch": "Generated code patch",
    "passed_reproducing_test": true,
    "passed_build": true,
    "passed_existing_test": false,
    "passed_regression_test": true, 
    "passed_reproduction_test": true,
    "issue_response": "AI-generated issue response"
  },
   "created_branch_and_pushed": true,
   "branch_name": "fix-issue-123"
}
```

### Result Field Description
- `success`: Whether the process was successful
- `issue_info`: Basic information about the GitHub issue
- `prometheus_result.patch`: Code fix patch generated by Prometheus
- `prometheus_result.passed_*`: Status of various validations
- `prometheus_result.issue_response`: AI-generated issue analysis and response
