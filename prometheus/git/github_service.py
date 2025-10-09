import json
import tempfile
from pathlib import Path
from typing import Dict, Optional

import aiohttp

from prometheus.configuration.github import github_settings
from prometheus.exceptions.github_exception import GithubException
from prometheus.utils.github_sec import create_github_jwt
from prometheus.utils.logger_manager import get_logger

logger = get_logger(__name__)


class GitHubService:
    """Service for GitHub API operations."""
    
    def __init__(self):
        self.base_url = "https://api.github.com"
        self._installation_token: Optional[str] = None
        self._token_expires_at: Optional[float] = None
    
    async def get_installation_token(self, installation_id: int) -> str:
        """
        Get GitHub App installation token.
        
        Args:
            installation_id: GitHub App installation ID
            
        Returns:
            str: Installation access token
        """
        jwt_token = create_github_jwt()
        
        url = f"{self.base_url}/app/installations/{installation_id}/access_tokens"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"{github_settings.BOT_HANDLE}-bot"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers) as response:
                if response.status != 201:
                    error_text = await response.text()
                    raise GithubException(
                        f"Failed to get installation token: {response.status} - {error_text}"
                    )
                
                data = await response.json()
                return data["token"]
    
    async def check_org_membership(self, username: str, org_name: str, token: str) -> bool:
        """
        Check if user is a member of the organization.
        
        Args:
            username: GitHub username
            org_name: Organization name
            token: GitHub token
            
        Returns:
            bool: True if user is a member, False otherwise
        """
        url = f"{self.base_url}/orgs/{org_name}/members/{username}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"{github_settings.BOT_HANDLE}-bot"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                # 204 = public member, 302 = private member, 404 = not a member
                return response.status in [204, 302]
    
    async def post_comment(self, owner: str, repo: str, issue_number: int, body: str, token: str) -> Dict:
        """
        Post a comment on an issue or PR.
        
        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue or PR number
            body: Comment body
            token: GitHub token
            
        Returns:
            Dict: Comment data from GitHub API
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_number}/comments"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"{github_settings.BOT_HANDLE}-bot"
        }
        
        payload = {"body": body}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 201:
                    error_text = await response.text()
                    raise GithubException(
                        f"Failed to post comment: {response.status} - {error_text}"
                    )
                
                return await response.json()
    
    async def update_comment(self, owner: str, repo: str, comment_id: int, body: str, token: str) -> Dict:
        """
        Update an existing comment.
        
        Args:
            owner: Repository owner
            repo: Repository name
            comment_id: Comment ID
            body: New comment body
            token: GitHub token
            
        Returns:
            Dict: Updated comment data from GitHub API
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/comments/{comment_id}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"{github_settings.BOT_HANDLE}-bot"
        }
        
        payload = {"body": body}
        
        async with aiohttp.ClientSession() as session:
            async with session.patch(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise GithubException(
                        f"Failed to update comment: {response.status} - {error_text}"
                    )
                
                return await response.json()
    
    async def create_branch(self, owner: str, repo: str, branch_name: str, base_sha: str, token: str) -> Dict:
        """
        Create a new branch.
        
        Args:
            owner: Repository owner
            repo: Repository name
            branch_name: Name of the new branch
            base_sha: SHA of the base commit
            token: GitHub token
            
        Returns:
            Dict: Branch creation response
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/git/refs"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"{github_settings.BOT_HANDLE}-bot"
        }
        
        payload = {
            "ref": f"refs/heads/{branch_name}",
            "sha": base_sha
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 201:
                    error_text = await response.text()
                    raise GithubException(
                        f"Failed to create branch: {response.status} - {error_text}"
                    )
                
                return await response.json()
    
    async def create_pull_request(
        self, 
        owner: str, 
        repo: str, 
        title: str, 
        body: str, 
        head_branch: str, 
        base_branch: str, 
        token: str
    ) -> Dict:
        """
        Create a pull request.
        
        Args:
            owner: Repository owner
            repo: Repository name
            title: PR title
            body: PR body
            head_branch: Source branch
            base_branch: Target branch
            token: GitHub token
            
        Returns:
            Dict: Pull request data from GitHub API
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"{github_settings.BOT_HANDLE}-bot"
        }
        
        payload = {
            "title": title,
            "body": body,
            "head": head_branch,
            "base": base_branch
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 201:
                    error_text = await response.text()
                    raise GithubException(
                        f"Failed to create pull request: {response.status} - {error_text}"
                    )
                
                return await response.json()
    
    async def get_repository_default_branch(self, owner: str, repo: str, token: str) -> str:
        """
        Get the default branch of a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            token: GitHub token
            
        Returns:
            str: Default branch name
        """
        url = f"{self.base_url}/repos/{owner}/{repo}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"{github_settings.BOT_HANDLE}-bot"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise GithubException(
                        f"Failed to get repository info: {response.status} - {error_text}"
                    )
                
                data = await response.json()
                return data["default_branch"]
    
    async def get_latest_commit_sha(self, owner: str, repo: str, branch: str, token: str) -> str:
        """
        Get the latest commit SHA for a branch.
        
        Args:
            owner: Repository owner
            repo: Repository name
            branch: Branch name
            token: GitHub token
            
        Returns:
            str: Latest commit SHA
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/git/refs/heads/{branch}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"{github_settings.BOT_HANDLE}-bot"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise GithubException(
                        f"Failed to get latest commit: {response.status} - {error_text}"
                    )
                
                data = await response.json()
                return data["object"]["sha"]