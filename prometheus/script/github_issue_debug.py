"""
GitHub Issue Auto Debug Script

This script automatically retrieves issue information from GitHub, uploads the repository to Prometheus, and sends the issue for debug analysis.

Usage:
    python github_issue_debug.py --github-token YOUR_TOKEN --repo owner/repo --issue-number 42

Parameter Description:
    --github-token: GitHub Personal Access Token (required)
    --repo: GitHub repository (format: owner/repo) (required)
    --issue-number: Issue number (required)
    --prometheus-url: Prometheus service address (default: http://localhost:9002/v1.2)
    --output-file: Result output file (optional, default outputs to console)
    --run-build: Whether to run build validation (default: False)
    --run-test: Whether to run test validation (default: False)
    --run-reproduction-test: Whether to run reproduction test (default: False)
    --run-regression-test: Whether to run regression test (default: False)
    --push-to-remote: Whether to push the fix to a remote branch (default: False)
"""

import argparse
import asyncio
import json
import sys
from typing import Dict

import requests

from prometheus.utils.github_utils import get_github_issue

REPOSITORY_UPLOAD_ENDPOINT = "/repository/upload/"
ISSUE_ANSWER_ENDPOINT = "/issue/answer/"
CREATE_BRANCH_AND_PUSH_ENDPOINT = "/repository/create-branch-and-push/"


class GitHubIssueDebugger:
    def __init__(self, github_token: str, prometheus_url: str = "http://localhost:9002/v1.2"):
        """
        Initialize GitHub Issue Debugger

        Args:
            github_token: GitHub Personal Access Token
            prometheus_url: Prometheus service URL
        """
        self.github_token = github_token
        self.prometheus_url = prometheus_url.rstrip("/")
        self.github_headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
        }
        self.prometheus_headers = {"Content-Type": "application/json"}

    def get_github_issue(self, repo: str, issue_number: int) -> Dict:
        """
        Retrieve issue information from GitHub

        Args:
            repo: Repository name (format: owner/repo)
            issue_number: Issue number

        Returns:
            A dictionary containing issue information
        """
        print(f"Retrieving GitHub issue: {repo}#{issue_number}")

        # Retrieve basic issue information
        return asyncio.run(get_github_issue(repo, issue_number, self.github_token))

    def upload_repository_to_prometheus(self, repo: str) -> int:
        """
        Upload GitHub repository to Prometheus

        Args:
            repo: Repository name (format: owner/repo)

        Returns:
            repository_id: ID of the uploaded repository in Prometheus
        """
        print(f"Uploading repository to Prometheus: {repo}")

        # Construct GitHub HTTPS URL
        github_url = f"https://github.com/{repo}.git"

        # Call Prometheus API to upload repository
        upload_url = self.prometheus_url + REPOSITORY_UPLOAD_ENDPOINT
        params = {"https_url": github_url, "commit_id": None, "github_token": self.github_token}

        response = requests.post(upload_url, json=params, headers=self.prometheus_headers)

        if response.status_code == 200:
            print("Repository uploaded successfully")
            return response.json()["data"]["repository_id"]
        else:
            raise Exception(
                f"Failed to upload repository: {response.status_code} - {response.text}"
            )

    def send_issue_to_prometheus(self, repository_id: int, issue_data: Dict, config: Dict) -> Dict:
        """
        Send issue to Prometheus for debugging

        Args:
            repository_id: GitHub repository id
            issue_data: GitHub issue data
            config: Configuration parameters

        Returns:
            Response from Prometheus
        """
        print("Sending issue to Prometheus for debug analysis...")

        # Construct Prometheus API request data
        request_data = {
            "repository_id": repository_id,
            "issue_title": issue_data["title"],
            "issue_body": issue_data["body"],
            "issue_comments": issue_data["comments"],
            "issue_type": "auto",
            "run_build": config.get("run_build", False),
            "run_existing_test": config.get("run_test", False),
            "run_regression_test": config.get("run_regression_test", True),
            "run_reproduce_test": config.get("run_reproduce_test", True),
            "number_of_candidate_patch": config.get("candidate_patches", 6),
        }

        # Add Docker configuration if present
        if "dockerfile_content" in config:
            request_data["dockerfile_content"] = config["dockerfile_content"]
            request_data["workdir"] = config.get("workdir", "/app")
        elif "image_name" in config:
            request_data["image_name"] = config["image_name"]
            request_data["workdir"] = config.get("workdir", "/app")

        if "build_commands" in config:
            request_data["build_commands"] = config["build_commands"]

        if "test_commands" in config:
            request_data["test_commands"] = config["test_commands"]

        # Send request to Prometheus
        answer_url = self.prometheus_url + ISSUE_ANSWER_ENDPOINT
        response = requests.post(answer_url, json=request_data, headers=self.prometheus_headers)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(
                f"Prometheus processing failed: {response.status_code} - {response.text}"
            )

    def create_branch_and_push(
        self, repo_id: int, branch_name: str, commit_message: str, patch: str
    ):
        """
        Create a new branch and push the patch to remote repository

        Args:
            repo_id: Repository ID in Prometheus
            branch_name: Name of the new branch
            commit_message: Commit message
            patch: Patch content to be applied

        Returns:
            Response from Prometheus
        """
        print(f"Pushing fix to remote branch: {branch_name}")

        push_url = self.prometheus_url + CREATE_BRANCH_AND_PUSH_ENDPOINT
        push_data = {
            "repository_id": repo_id,
            "branch_name": branch_name,
            "commit_message": commit_message,
            "patch": patch,
        }

        response = requests.post(push_url, json=push_data, headers=self.prometheus_headers)

        if response.status_code == 200:
            print("Patch pushed successfully")
        else:
            raise Exception(f"Failed to push patch: {response.status_code} - {response.text}")

    def process_issue(self, repo: str, issue_number: int, config: Dict) -> Dict:
        """
        Complete issue processing workflow

        Args:
            repo: Repository name
            issue_number: Issue number
            config: Configuration parameters

        Returns:
            Processing result
        """
        try:
            # 1. Retrieve GitHub issue
            issue_data = self.get_github_issue(repo, issue_number)

            # 2. Upload repository to Prometheus
            repository_id = self.upload_repository_to_prometheus(repo)

            # 3. Send issue to Prometheus for debugging
            result = self.send_issue_to_prometheus(repository_id, issue_data, config)
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "issue_info": {"repo": repo, "number": issue_number},
            }

        # 4. Upload it to GitHub if needed
        created_branch_and_pushed = False
        branch_name = f"fix-issue-{issue_number}"
        if config.get("push_to_remote", False) and result["data"].get("patch"):
            patch = result["data"]["patch"]
            commit_message = f"Fix issue #{issue_number}: {issue_data['title']}"

            try:
                self.create_branch_and_push(repository_id, branch_name, commit_message, patch)
                created_branch_and_pushed = True
            except Exception:
                created_branch_and_pushed = False

        # 5. Integrate results
        return {
            "success": True,
            "issue_info": {
                "repo": repo,
                "number": issue_data["number"],
                "title": issue_data["title"],
                "url": issue_data["html_url"],
                "state": issue_data["state"],
            },
            "prometheus_result": result,
            "created_branch_and_pushed": created_branch_and_pushed,
            "branch_name": branch_name if created_branch_and_pushed else None,
        }


def main():
    parser = argparse.ArgumentParser(
        description="GitHub Issue Auto Debug Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument("--github-token", required=True, help="GitHub Personal Access Token")

    parser.add_argument("--repo", required=True, help="GitHub repository (format: owner/repo)")

    parser.add_argument("--issue-number", type=int, required=True, help="Issue number")

    parser.add_argument(
        "--prometheus-url",
        default="http://localhost:9002/v1.2",
        help="Prometheus service address (default: http://localhost:9002/v1.2)",
    )

    parser.add_argument(
        "--output-file",
        help="Path to the result output file (optional, default outputs to console)",
    )

    parser.add_argument("--run-build", action="store_true", help="Run build validation")

    parser.add_argument("--run-test", action="store_true", help="Run test validation")

    parser.add_argument(
        "--run-reproduction-test",
        action="store_true",
        help="Run reproduction test",
    )

    parser.add_argument(
        "--run-regression-test",
        action="store_true",
        help="Run regression test",
    )

    parser.add_argument("--push-to-remote", action="store_true", help="Push fix to remote branch")

    parser.add_argument(
        "--dockerfile-content", help="Dockerfile content (for specifying container environment)"
    )

    parser.add_argument(
        "--image-name", help="Docker image name (for specifying container environment)"
    )

    parser.add_argument(
        "--workdir",
        default="/app",
        help="Working directory (required when using container environment)",
    )

    parser.add_argument("--build-commands", nargs="+", help="List of build commands")

    parser.add_argument("--test-commands", nargs="+", help="List of test commands")

    parser.add_argument(
        "--candidate-patches", type=int, default=6, help="Number of candidate patches (default: 6)"
    )

    args = parser.parse_args()

    # Validate repo format
    if "/" not in args.repo:
        print("Error: Invalid repo format, should be 'owner/repo'")
        sys.exit(1)

    # Build configuration
    config = {
        "run_build": args.run_build,
        "run_test": args.run_test,
        "run_reproduce_test": args.run_reproduction_test,
        "run_regression_test": args.run_regression_test,
        "push_to_remote": args.push_to_remote,
        "candidate_patches": args.candidate_patches,
        "workdir": args.workdir,
    }

    if args.dockerfile_content:
        config["dockerfile_content"] = args.dockerfile_content

    if args.image_name:
        config["image_name"] = args.image_name

    if args.build_commands:
        config["build_commands"] = args.build_commands

    if args.test_commands:
        config["test_commands"] = args.test_commands

    # Create debugger and process issue
    debugger = GitHubIssueDebugger(args.github_token, args.prometheus_url)
    result = debugger.process_issue(args.repo, args.issue_number, config)

    # Output results
    if args.output_file:
        with open(args.output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"Results saved to: {args.output_file}")
    else:
        print("\n" + "=" * 60)
        print("Processing Results:")
        print("=" * 60)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    # Simplified summary output
    print("\n" + "=" * 60)
    print("Execution Summary:")
    print("=" * 60)

    if result["success"]:
        issue_info = result["issue_info"]
        prometheus_result = result["prometheus_result"]

        print("✅ Successfully processed GitHub Issue")
        print(f"   Repository: {issue_info['repo']}")
        print(f"   Issue: #{issue_info['number']} - {issue_info['title']}")
        print(f"   URL: {issue_info['url']}")
        print(f"   State: {issue_info['state']}")

        if prometheus_result.get("patch"):
            print("✅ Generated fix patch")

        if prometheus_result.get("passed_existing_test") is not None:
            status = "✅ Passed" if prometheus_result["passed_existing_test"] else "❌ Failed"
            print(f"   Test Validation: {status}")

        if prometheus_result.get("passed_reproducing_test") is not None:
            status = "✅ Passed" if prometheus_result["passed_reproducing_test"] else "❌ Failed"
            print(f"   Reproducing Test: {status}")

        if prometheus_result.get("passed_regression_test") is not None:
            status = "✅ Passed" if prometheus_result["passed_regression_test"] else "❌ Failed"
            print(f"   Regression Test: {status}")

        if result.get("created_branch_and_pushed"):
            print("✅ Fix patch pushed to remote repository")
        else:
            if args.push_to_remote:
                print("⚠️  Failed to push fix patch to remote repository")
            else:
                print("ℹ️  Fix patch not pushed to remote repository (push_to_remote=False)")

        if prometheus_result.get("issue_response"):
            print("📝 Prometheus analysis result generated")

    else:
        print(f"❌ Processing failed: {result['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
