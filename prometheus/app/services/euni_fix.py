import asyncio
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from prometheus.utils.logger_manager import get_logger

logger = get_logger(__name__)


class EuniFixResult:
    """Result of the EuniFix operation."""
    
    def __init__(
        self, 
        success: bool, 
        message: str, 
        files_changed: Optional[List[str]] = None,
        commit_sha: Optional[str] = None,
        error: Optional[str] = None
    ):
        self.success = success
        self.message = message
        self.files_changed = files_changed or []
        self.commit_sha = commit_sha
        self.error = error


async def run_euni_fix(repo_dir: str, args: str, issue_context: Optional[Dict] = None) -> EuniFixResult:
    """
    Placeholder for EuniFix auto-fix logic.
    
    This function will be replaced with actual AI agent integration.
    Currently returns a mock result for testing purposes.
    
    Args:
        repo_dir: Path to the cloned repository
        args: Arguments passed with the /fix command
        issue_context: Optional context about the issue/PR
        
    Returns:
        EuniFixResult: Result of the fix operation
    """
    logger.info(f"Running EuniFix in directory: {repo_dir}")
    logger.info(f"Fix arguments: {args}")
    
    try:
        # Simulate some processing time
        await asyncio.sleep(2)
        
        # Mock implementation - replace with actual AI agent logic
        
        # Example: Check if there are any Python files to fix
        repo_path = Path(repo_dir)
        python_files = list(repo_path.rglob("*.py"))
        
        if not python_files:
            return EuniFixResult(
                success=False,
                message="No Python files found to fix",
                error="Repository does not contain Python files"
            )
        
        # Mock: Simulate fixing some files
        files_to_fix = python_files[:min(3, len(python_files))]  # Fix up to 3 files
        files_changed = []
        
        for file_path in files_to_fix:
            # Mock: Add a comment to the file
            try:
                content = file_path.read_text()
                if "# Fixed by EuniBot" not in content:
                    # Add a comment at the top
                    fixed_content = f"# Fixed by EuniBot - {args if args else 'General fix'}\n" + content
                    file_path.write_text(fixed_content)
                    files_changed.append(str(file_path.relative_to(repo_path)))
                    logger.info(f"Fixed file: {file_path}")
            except Exception as e:
                logger.error(f"Error fixing file {file_path}: {e}")
        
        if files_changed:
            return EuniFixResult(
                success=True,
                message=f"Successfully applied fixes to {len(files_changed)} files",
                files_changed=files_changed
            )
        else:
            return EuniFixResult(
                success=False,
                message="No changes were needed or could be applied",
                error="All files were already up to date"
            )
    
    except Exception as e:
        logger.error(f"Error running EuniFix: {e}")
        return EuniFixResult(
            success=False,
            message="Failed to run EuniFix",
            error=str(e)
        )


async def commit_changes(repo_dir: str, files_changed: List[str], commit_message: str) -> Optional[str]:
    """
    Commit changes to the repository.
    
    Args:
        repo_dir: Path to the repository
        files_changed: List of files that were changed
        commit_message: Commit message
        
    Returns:
        Optional[str]: Commit SHA if successful, None otherwise
    """
    try:
        # Use git commands to commit changes
        import subprocess
        
        # Change to repo directory
        original_cwd = os.getcwd()
        os.chdir(repo_dir)
        
        try:
            # Add changed files
            for file_path in files_changed:
                result = subprocess.run(['git', 'add', file_path], capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error(f"Failed to add file {file_path}: {result.stderr}")
                    return None
            
            # Commit changes
            result = subprocess.run(
                ['git', 'commit', '-m', commit_message],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to commit changes: {result.stderr}")
                return None
            
            # Get the commit SHA
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                logger.error(f"Failed to get commit SHA: {result.stderr}")
                return None
        
        finally:
            os.chdir(original_cwd)
    
    except Exception as e:
        logger.error(f"Error committing changes: {e}")
        return None


async def clone_repository(repo_url: str, branch: str = "main") -> str:
    """
    Clone a repository to a temporary directory.
    
    Args:
        repo_url: Repository URL
        branch: Branch to clone
        
    Returns:
        str: Path to the cloned repository
    """
    try:
        import subprocess
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix="euni_fix_")
        
        # Clone repository
        result = subprocess.run(
            ['git', 'clone', '-b', branch, repo_url, temp_dir],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"Failed to clone repository: {result.stderr}")
            raise Exception(f"Git clone failed: {result.stderr}")
        
        logger.info(f"Repository cloned to: {temp_dir}")
        return temp_dir
    
    except Exception as e:
        logger.error(f"Error cloning repository: {e}")
        raise


async def push_to_branch(repo_dir: str, branch_name: str, remote_url: str) -> bool:
    """
    Push changes to a remote branch.
    
    Args:
        repo_dir: Path to the repository
        branch_name: Branch name to push to
        remote_url: Remote repository URL
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        import subprocess
        
        original_cwd = os.getcwd()
        os.chdir(repo_dir)
        
        try:
            # Create and checkout new branch
            result = subprocess.run(
                ['git', 'checkout', '-b', branch_name],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to create branch {branch_name}: {result.stderr}")
                return False
            
            # Push to remote
            result = subprocess.run(
                ['git', 'push', '-u', 'origin', branch_name],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to push branch {branch_name}: {result.stderr}")
                return False
            
            logger.info(f"Successfully pushed branch: {branch_name}")
            return True
        
        finally:
            os.chdir(original_cwd)
    
    except Exception as e:
        logger.error(f"Error pushing to branch: {e}")
        return False