import hashlib
import hmac
import jwt
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from prometheus.configuration.github import github_settings
from prometheus.exceptions.github_exception import GithubException


def verify_webhook_signature(payload_body: bytes, signature_header: str) -> bool:
    """
    Verify GitHub webhook signature.
    
    Args:
        payload_body: Raw request body bytes
        signature_header: X-Hub-Signature-256 header value
        
    Returns:
        bool: True if signature is valid, False otherwise
    """
    if not signature_header:
        return False
    
    # Extract the signature from the header (format: sha256=<signature>)
    try:
        algorithm, signature = signature_header.split('=', 1)
        if algorithm != 'sha256':
            return False
    except ValueError:
        return False
    
    # Calculate expected signature
    expected_signature = hmac.new(
        github_settings.WEBHOOK_SECRET.encode('utf-8'),
        payload_body,
        hashlib.sha256
    ).hexdigest()
    
    # Compare signatures using secure comparison
    return hmac.compare_digest(expected_signature, signature)


def create_github_jwt() -> str:
    """
    Create a JWT token for GitHub App authentication.
    
    Returns:
        str: JWT token for GitHub App
    """
    # JWT expires in 10 minutes (GitHub's maximum)
    now = datetime.now(timezone.utc)
    expiration = now + timedelta(minutes=10)
    
    payload = {
        'iat': int(now.timestamp()),
        'exp': int(expiration.timestamp()),
        'iss': github_settings.APP_ID
    }
    
    # GitHub expects RS256 algorithm
    try:
        token = jwt.encode(payload, github_settings.PRIVATE_KEY, algorithm='RS256')
        return token
    except Exception as e:
        raise GithubException(f"Failed to create GitHub JWT: {str(e)}")


def parse_fix_command(comment_body: str, bot_handle: str) -> Optional[Tuple[str, str]]:
    """
    Parse `/fix` command from comment body.
    
    Args:
        comment_body: The comment body text
        bot_handle: The GitHub bot handle (username)
        
    Returns:
        Optional[Tuple[str, str]]: (command, arguments) if found, None otherwise
    """
    if not comment_body:
        return None
    
    # Pattern to match @bot-handle /fix [optional args]
    # Case insensitive matching
    pattern = rf'@{re.escape(bot_handle)}\s+/fix(?:\s+(.+))?'
    
    match = re.search(pattern, comment_body, re.IGNORECASE | re.MULTILINE)
    if match:
        args = match.group(1) or ""  # Get arguments or empty string
        return ("fix", args.strip())
    
    return None


def extract_repository_info(repository_url: str) -> Tuple[str, str]:
    """
    Extract owner and repo name from repository URL.
    
    Args:
        repository_url: GitHub repository URL
        
    Returns:
        Tuple[str, str]: (owner, repo_name)
    """
    # Handle both https and git URLs
    # Examples:
    # https://github.com/owner/repo
    # git@github.com:owner/repo.git
    
    if repository_url.startswith('https://github.com/'):
        parts = repository_url.replace('https://github.com/', '').split('/')
        if len(parts) >= 2:
            return parts[0], parts[1]
    elif repository_url.startswith('git@github.com:'):
        repo_part = repository_url.replace('git@github.com:', '').replace('.git', '')
        parts = repo_part.split('/')
        if len(parts) >= 2:
            return parts[0], parts[1]
    
    raise GithubException(f"Invalid repository URL format: {repository_url}")