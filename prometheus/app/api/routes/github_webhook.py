import asyncio
import json
import tempfile
import uuid
from datetime import datetime
from typing import Dict

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from prometheus.app.services.euni_fix import (
    EuniFixResult,
    clone_repository,
    commit_changes,
    push_to_branch,
    run_euni_fix,
)
from prometheus.configuration.github import github_settings
from prometheus.git.github_service import GitHubService
from prometheus.utils.github_sec import parse_fix_command, verify_webhook_signature
from prometheus.utils.logger_manager import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Handle GitHub webhook events.
    
    Listens for issue_comment events and processes /fix commands.
    """
    # Get raw request body for signature verification
    body = await request.body()
    
    # Verify webhook signature
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_webhook_signature(body, signature):
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Parse JSON payload
    try:
        payload = json.loads(body.decode('utf-8'))
    except json.JSONDecodeError:
        logger.error("Invalid JSON payload")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    # Check event type
    event_type = request.headers.get("X-GitHub-Event")
    if event_type != "issue_comment":
        logger.info(f"Ignoring event type: {event_type}")
        return {"message": "Event type not supported"}
    
    # Check if it's a comment creation event
    action = payload.get("action")
    if action != "created":
        logger.info(f"Ignoring comment action: {action}")
        return {"message": "Action not supported"}
    
    # Extract comment data
    comment = payload.get("comment", {})
    comment_body = comment.get("body", "")
    comment_author = comment.get("user", {}).get("login", "")
    
    # Check for /fix command
    fix_command = parse_fix_command(comment_body, github_settings.BOT_HANDLE)
    if not fix_command:
        logger.info("No /fix command found in comment")
        return {"message": "No fix command found"}
    
    command, args = fix_command
    logger.info(f"Fix command detected: {command} with args: {args}")
    
    # Extract repository and issue information
    repository = payload.get("repository", {})
    issue = payload.get("issue", {})
    
    repo_owner = repository.get("owner", {}).get("login", "")
    repo_name = repository.get("name", "")
    repo_full_name = repository.get("full_name", "")
    repo_clone_url = repository.get("clone_url", "")
    installation_id = payload.get("installation", {}).get("id")
    
    issue_number = issue.get("number")
    issue_title = issue.get("title", "")
    is_pull_request = "pull_request" in issue
    
    if not all([repo_owner, repo_name, installation_id, issue_number]):
        logger.error("Missing required webhook data")
        raise HTTPException(status_code=400, detail="Missing required data")
    
    # Start background task to process the fix
    background_tasks.add_task(
        process_fix_request,
        installation_id=installation_id,
        repo_owner=repo_owner,
        repo_name=repo_name,
        repo_clone_url=repo_clone_url,
        issue_number=issue_number,
        issue_title=issue_title,
        is_pull_request=is_pull_request,
        fix_args=args,
        comment_author=comment_author,
        issue_context=issue
    )
    
    return {"message": "Fix request received and processing"}


async def process_fix_request(
    installation_id: int,
    repo_owner: str,
    repo_name: str,
    repo_clone_url: str,
    issue_number: int,
    issue_title: str,
    is_pull_request: bool,
    fix_args: str,
    comment_author: str,
    issue_context: Dict
):
    """
    Background task to process the fix request.
    """
    github_service = GitHubService()
    temp_repo_dir = None
    
    try:
        logger.info(f"Processing fix request for {repo_owner}/{repo_name}#{issue_number}")
        
        # Get installation token
        token = await github_service.get_installation_token(installation_id)
        
        # Check organization membership if ORG_NAME is set
        if github_settings.ORG_NAME:
            is_member = await github_service.check_org_membership(
                comment_author, github_settings.ORG_NAME, token
            )
            if not is_member:
                await github_service.post_comment(
                    repo_owner, repo_name, issue_number,
                    f"❌ @{comment_author} is not a member of the {github_settings.ORG_NAME} organization.",
                    token
                )
                return
        
        # Post placeholder comment
        placeholder_comment = await github_service.post_comment(
            repo_owner, repo_name, issue_number,
            f"🤖 EuniBot is analyzing the issue and preparing fixes...\n\n"
            f"Requested by: @{comment_author}\n"
            f"Arguments: `{fix_args if fix_args else 'None'}`\n\n"
            f"⏳ This may take a few minutes.",
            token
        )
        
        comment_id = placeholder_comment["id"]
        
        # Get default branch
        default_branch = await github_service.get_repository_default_branch(
            repo_owner, repo_name, token
        )
        
        # Clone repository
        temp_repo_dir = await clone_repository(repo_clone_url, default_branch)
        
        # Run EuniFix
        fix_result = await run_euni_fix(temp_repo_dir, fix_args, issue_context)
        
        if fix_result.success and fix_result.files_changed:
            # Generate unique branch name
            branch_name = f"euni-fix-{issue_number}-{uuid.uuid4().hex[:8]}"
            
            # Commit changes
            commit_message = f"🤖 EuniFix: {issue_title}\n\nFixes #{issue_number}\nRequested by: @{comment_author}"
            if fix_args:
                commit_message += f"\nArguments: {fix_args}"
            
            commit_sha = await commit_changes(temp_repo_dir, fix_result.files_changed, commit_message)
            
            if commit_sha:
                # Get latest commit SHA from default branch
                base_sha = await github_service.get_latest_commit_sha(
                    repo_owner, repo_name, default_branch, token
                )
                
                # Create new branch
                await github_service.create_branch(
                    repo_owner, repo_name, branch_name, base_sha, token
                )
                
                # Push changes to the new branch
                authenticated_clone_url = repo_clone_url.replace(
                    "https://", f"https://x-access-token:{token}@"
                )
                push_success = await push_to_branch(
                    temp_repo_dir, branch_name, authenticated_clone_url
                )
                
                if push_success:
                    # Create pull request
                    pr_title = f"🤖 EuniFix: {issue_title}"
                    pr_body = (
                        f"This PR was automatically generated by EuniBot to fix issue #{issue_number}.\n\n"
                        f"## Changes Made\n"
                        f"- {fix_result.message}\n\n"
                        f"## Files Modified\n"
                    )
                    for file_path in fix_result.files_changed:
                        pr_body += f"- `{file_path}`\n"
                    
                    pr_body += f"\n## Requested by\n@{comment_author}"
                    if fix_args:
                        pr_body += f"\n\n## Arguments\n`{fix_args}`"
                    
                    pr_body += f"\n\nCloses #{issue_number}"
                    
                    pr = await github_service.create_pull_request(
                        repo_owner, repo_name, pr_title, pr_body,
                        branch_name, default_branch, token
                    )
                    
                    # Update placeholder comment with success
                    success_message = (
                        f"✅ **EuniFix completed successfully!**\n\n"
                        f"📋 **Summary**: {fix_result.message}\n"
                        f"🔧 **Files modified**: {len(fix_result.files_changed)}\n"
                        f"🌿 **Branch**: `{branch_name}`\n"
                        f"🔗 **Pull Request**: #{pr['number']} - {pr['html_url']}\n\n"
                        f"**Modified files:**\n"
                    )
                    for file_path in fix_result.files_changed:
                        success_message += f"- `{file_path}`\n"
                    
                    await github_service.update_comment(
                        repo_owner, repo_name, comment_id, success_message, token
                    )
                    
                    logger.info(f"Successfully created PR #{pr['number']} for fix request")
                else:
                    raise Exception("Failed to push changes to branch")
            else:
                raise Exception("Failed to commit changes")
        else:
            # Update placeholder comment with failure
            error_message = (
                f"❌ **EuniFix failed**\n\n"
                f"📋 **Message**: {fix_result.message}\n"
            )
            if fix_result.error:
                error_message += f"🚨 **Error**: {fix_result.error}\n"
            
            error_message += f"\nRequested by: @{comment_author}"
            
            await github_service.update_comment(
                repo_owner, repo_name, comment_id, error_message, token
            )
            
            logger.error(f"EuniFix failed: {fix_result.message}")
    
    except Exception as e:
        logger.error(f"Error processing fix request: {e}")
        
        try:
            # Try to update the placeholder comment with error
            error_message = (
                f"❌ **EuniFix encountered an error**\n\n"
                f"🚨 **Error**: {str(e)}\n"
                f"Requested by: @{comment_author}\n\n"
                f"Please try again or contact support if the issue persists."
            )
            
            # Get token again if needed
            if 'token' not in locals():
                token = await github_service.get_installation_token(installation_id)
            
            if 'comment_id' in locals():
                await github_service.update_comment(
                    repo_owner, repo_name, comment_id, error_message, token
                )
        except Exception as update_error:
            logger.error(f"Failed to update error comment: {update_error}")
    
    finally:
        # Clean up temporary directory
        if temp_repo_dir:
            try:
                import shutil
                shutil.rmtree(temp_repo_dir)
                logger.info(f"Cleaned up temporary directory: {temp_repo_dir}")
            except Exception as cleanup_error:
                logger.error(f"Failed to cleanup temp directory: {cleanup_error}")