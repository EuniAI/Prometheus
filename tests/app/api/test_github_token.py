from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from prometheus.app.api.routes.github import router

# Create test app
app = FastAPI()
app.include_router(router, prefix="/github")
client = TestClient(app)


@pytest.fixture
def mock_issue_data():
    """Fixture for mock issue data."""
    return {
        "number": 123,
        "title": "Test Issue",
        "body": "This is a test issue body",
        "state": "open",
        "html_url": "https://github.com/owner/repo/issues/123",
        "comments": [
            {"username": "user1", "comment": "First comment"},
            {"username": "user2", "comment": "Second comment"},
        ],
    }


def test_get_github_issue_success(mock_issue_data):
    """Test successful retrieval of GitHub issue through the API endpoint."""

    with patch("prometheus.app.api.routes.github.get_github_issue") as mock_get_issue:
        # Configure the mock
        mock_get_issue.return_value = mock_issue_data

        # Make the request
        response = client.get(
            "/github/issue/",
            params={"repo": "owner/repo", "issue_number": 123, "github_token": "test_token"},
        )

        # Assert response status
        assert response.status_code == 200

        # Parse response
        response_data = response.json()

        # Assert response structure
        assert "data" in response_data
        assert "message" in response_data
        assert "code" in response_data

        # Assert data content
        data = response_data["data"]
        assert data["number"] == 123
        assert data["title"] == "Test Issue"
        assert data["body"] == "This is a test issue body"
        assert data["state"] == "open"
        assert len(data["comments"]) == 2
        assert data["comments"][0]["username"] == "user1"

        # Verify the function was called with correct parameters
        mock_get_issue.assert_called_once_with("owner/repo", 123, "test_token")
