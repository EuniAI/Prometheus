import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from prometheus.app.api.routes.github_webhook import router
from prometheus.utils.github_sec import parse_fix_command, verify_webhook_signature

# Mock webhook payload
MOCK_ISSUE_COMMENT_PAYLOAD = {
    "action": "created",
    "issue": {"number": 123, "title": "Test issue", "state": "open"},
    "comment": {
        "id": 456,
        "body": "@euni-bot /fix Please fix the formatting issues",
        "user": {"login": "test-user"},
    },
    "repository": {
        "name": "test-repo",
        "full_name": "test-owner/test-repo",
        "clone_url": "https://github.com/test-owner/test-repo.git",
        "owner": {"login": "test-owner"},
    },
    "installation": {"id": 123456},
}


class TestGitHubWebhook:
    def test_parse_fix_command_valid(self):
        """Test parsing valid /fix commands."""
        # Basic /fix command
        comment_body = "@euni-bot /fix"
        result = parse_fix_command(comment_body, "euni-bot")
        assert result == ("fix", "")

        # /fix command with arguments
        comment_body = "@euni-bot /fix --strict --format"
        result = parse_fix_command(comment_body, "euni-bot")
        assert result == ("fix", "--strict --format")

        # Case insensitive
        comment_body = "@EUNI-BOT /FIX test args"
        result = parse_fix_command(comment_body, "euni-bot")
        assert result == ("fix", "test args")

        # With other text around
        comment_body = "Some text before\n@euni-bot /fix urgent\nSome text after"
        result = parse_fix_command(comment_body, "euni-bot")
        assert result == ("fix", "urgent")

    def test_parse_fix_command_invalid(self):
        """Test parsing invalid /fix commands."""
        # Wrong bot handle
        comment_body = "@other-bot /fix"
        result = parse_fix_command(comment_body, "euni-bot")
        assert result is None

        # No @ mention
        comment_body = "euni-bot /fix"
        result = parse_fix_command(comment_body, "euni-bot")
        assert result is None

        # Different command
        comment_body = "@euni-bot /help"
        result = parse_fix_command(comment_body, "euni-bot")
        assert result is None

        # Empty comment
        result = parse_fix_command("", "euni-bot")
        assert result is None

        # None comment
        result = parse_fix_command(None, "euni-bot")
        assert result is None

    def test_verify_webhook_signature_valid(self):
        """Test webhook signature verification with valid signature."""
        payload = b'{"test": "data"}'
        secret = "test-secret"

        # Mock the github_settings
        with patch("prometheus.utils.github_sec.github_settings") as mock_settings:
            mock_settings.WEBHOOK_SECRET = secret

            import hashlib
            import hmac

            # Create valid signature
            expected_signature = hmac.new(
                secret.encode("utf-8"), payload, hashlib.sha256
            ).hexdigest()

            signature_header = f"sha256={expected_signature}"
            result = verify_webhook_signature(payload, signature_header)
            assert result is True

    def test_verify_webhook_signature_invalid(self):
        """Test webhook signature verification with invalid signature."""
        payload = b'{"test": "data"}'

        with patch("prometheus.utils.github_sec.github_settings") as mock_settings:
            mock_settings.WEBHOOK_SECRET = "test-secret"

            # Test with wrong signature
            result = verify_webhook_signature(payload, "sha256=wrong_signature")
            assert result is False

            # Test with no signature
            result = verify_webhook_signature(payload, "")
            assert result is False

            # Test with malformed signature
            result = verify_webhook_signature(payload, "malformed")
            assert result is False

    @pytest.mark.asyncio
    async def test_github_webhook_valid_fix_command(self):
        """Test webhook handling with valid /fix command."""
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        payload = json.dumps(MOCK_ISSUE_COMMENT_PAYLOAD).encode("utf-8")

        with patch("prometheus.utils.github_sec.verify_webhook_signature", return_value=True):
            with patch("prometheus.app.api.routes.github_webhook.process_fix_request"):
                response = client.post(
                    "/webhook",
                    content=payload,
                    headers={
                        "X-GitHub-Event": "issue_comment",
                        "X-Hub-Signature-256": "sha256=test_signature",
                        "Content-Type": "application/json",
                    },
                )

                assert response.status_code == 200
                assert response.json()["message"] == "Fix request received and processing"

    @pytest.mark.asyncio
    async def test_github_webhook_invalid_signature(self):
        """Test webhook rejection with invalid signature."""
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        payload = json.dumps(MOCK_ISSUE_COMMENT_PAYLOAD).encode("utf-8")

        with patch("prometheus.utils.github_sec.verify_webhook_signature", return_value=False):
            response = client.post(
                "/webhook",
                content=payload,
                headers={
                    "X-GitHub-Event": "issue_comment",
                    "X-Hub-Signature-256": "sha256=invalid_signature",
                    "Content-Type": "application/json",
                },
            )

            assert response.status_code == 401
            assert response.json()["detail"] == "Invalid signature"

    @pytest.mark.asyncio
    async def test_github_webhook_wrong_event_type(self):
        """Test webhook ignoring wrong event types."""
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        payload = json.dumps(MOCK_ISSUE_COMMENT_PAYLOAD).encode("utf-8")

        with patch("prometheus.utils.github_sec.verify_webhook_signature", return_value=True):
            response = client.post(
                "/webhook",
                content=payload,
                headers={
                    "X-GitHub-Event": "push",  # Wrong event type
                    "X-Hub-Signature-256": "sha256=test_signature",
                    "Content-Type": "application/json",
                },
            )

            assert response.status_code == 200
            assert response.json()["message"] == "Event type not supported"

    @pytest.mark.asyncio
    async def test_github_webhook_no_fix_command(self):
        """Test webhook ignoring comments without /fix command."""
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Modify payload to have no /fix command
        modified_payload = MOCK_ISSUE_COMMENT_PAYLOAD.copy()
        modified_payload["comment"]["body"] = "Just a regular comment"

        payload = json.dumps(modified_payload).encode("utf-8")

        with patch("prometheus.utils.github_sec.verify_webhook_signature", return_value=True):
            response = client.post(
                "/webhook",
                content=payload,
                headers={
                    "X-GitHub-Event": "issue_comment",
                    "X-Hub-Signature-256": "sha256=test_signature",
                    "Content-Type": "application/json",
                },
            )

            assert response.status_code == 200
            assert response.json()["message"] == "No fix command found"


class TestGitHubService:
    @pytest.mark.asyncio
    async def test_get_installation_token(self):
        """Test getting GitHub installation token."""
        from prometheus.git.github_service import GitHubService

        service = GitHubService()

        mock_response_data = {"token": "test_token_123", "expires_at": "2023-12-31T23:59:59Z"}

        with patch("prometheus.utils.github_sec.create_github_jwt", return_value="test_jwt"):
            with patch("aiohttp.ClientSession.post") as mock_post:
                mock_response = AsyncMock()
                mock_response.status = 201
                mock_response.json = AsyncMock(return_value=mock_response_data)
                mock_post.return_value.__aenter__.return_value = mock_response

                token = await service.get_installation_token(123456)
                assert token == "test_token_123"

    @pytest.mark.asyncio
    async def test_check_org_membership_member(self):
        """Test organization membership check for valid member."""
        from prometheus.git.github_service import GitHubService

        service = GitHubService()

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 204  # Public member
            mock_get.return_value.__aenter__.return_value = mock_response

            is_member = await service.check_org_membership("test-user", "test-org", "token")
            assert is_member is True

    @pytest.mark.asyncio
    async def test_check_org_membership_not_member(self):
        """Test organization membership check for non-member."""
        from prometheus.git.github_service import GitHubService

        service = GitHubService()

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 404  # Not a member
            mock_get.return_value.__aenter__.return_value = mock_response

            is_member = await service.check_org_membership("test-user", "test-org", "token")
            assert is_member is False

    @pytest.mark.asyncio
    async def test_post_comment(self):
        """Test posting a comment."""
        from prometheus.git.github_service import GitHubService

        service = GitHubService()

        mock_response_data = {"id": 789, "body": "Test comment", "user": {"login": "euni-bot"}}

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 201
            mock_response.json = AsyncMock(return_value=mock_response_data)
            mock_post.return_value.__aenter__.return_value = mock_response

            comment = await service.post_comment("owner", "repo", 123, "Test comment", "token")
            assert comment["id"] == 789
            assert comment["body"] == "Test comment"


class TestEuniFix:
    @pytest.mark.asyncio
    async def test_run_euni_fix_success(self):
        """Test successful EuniFix execution."""
        from prometheus.app.services.euni_fix import run_euni_fix

        with patch("prometheus.app.services.euni_fix.Path") as mock_path:
            # Mock some Python files in the repo
            mock_repo_path = Mock()
            mock_file1 = Mock()
            mock_file1.read_text.return_value = "print('hello')"
            mock_file1.relative_to.return_value = "test1.py"
            mock_file1.write_text = Mock()

            mock_path.return_value = mock_repo_path
            mock_repo_path.rglob.return_value = [mock_file1]

            result = await run_euni_fix("/tmp/test_repo", "test_args")

            assert result.success is True
            assert len(result.files_changed) == 1
            assert "test1.py" in result.files_changed

    @pytest.mark.asyncio
    async def test_run_euni_fix_no_python_files(self):
        """Test EuniFix with no Python files."""
        from prometheus.app.services.euni_fix import run_euni_fix

        with patch("prometheus.app.services.euni_fix.Path") as mock_path:
            mock_repo_path = Mock()
            mock_path.return_value = mock_repo_path
            mock_repo_path.rglob.return_value = []  # No Python files

            result = await run_euni_fix("/tmp/test_repo", "test_args")

            assert result.success is False
            assert "No Python files found" in result.message
            assert len(result.files_changed) == 0
