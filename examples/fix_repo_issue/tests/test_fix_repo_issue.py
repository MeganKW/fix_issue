import pathlib
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fix_repo_issue import (
    create_sample,
    fix_repo_issue,
    get_instructions,
    get_latest_commit_id,
    hash_content,
    pr_and_end,
)
from pytest_mock import MockerFixture

from inspect_ai import Task
from inspect_ai.dataset import Sample
from inspect_ai.model import ModelName
from inspect_ai.solver import TaskState


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock environment variables for all tests."""
    monkeypatch.setenv("GITHUB_TOKEN", "test_token")
    monkeypatch.setenv("REPO_URL", "https://github.com/owner/repo")


@pytest.fixture
def mock_commit_response() -> dict[str, Any]:
    return {
        "sha": "abc123def456",
        "node_id": "MDY6Q29tbWl0MTIzNDU2Nzg5",
        "commit": {
            "author": {
                "name": "Test Author",
                "email": "test@example.com",
                "date": "2024-01-01T00:00:00Z",
            },
            "committer": {
                "name": "Test Committer",
                "email": "committer@example.com",
                "date": "2024-01-01T00:00:00Z",
            },
            "message": "Test commit message",
            "tree": {
                "sha": "def456abc789",
                "url": "https://api.github.com/repos/owner/repo/git/trees/def456abc789",
            },
            "url": "https://api.github.com/repos/owner/repo/git/commits/abc123def456",
            "comment_count": 0,
        },
        "url": "https://api.github.com/repos/owner/repo/commits/abc123def456",
        "html_url": "https://github.com/owner/repo/commit/abc123def456",
        "comments_url": "https://api.github.com/repos/owner/repo/commits/abc123def456/comments",
    }


@pytest.fixture
def mock_issue_response() -> dict[str, Any]:
    return {
        "id": 1,
        "node_id": "MDU6SXNzdWUx",
        "url": "https://api.github.com/repos/owner/repo/issues/123",
        "repository_url": "https://api.github.com/repos/owner/repo",
        "labels_url": "https://api.github.com/repos/owner/repo/issues/123/labels{/name}",
        "comments_url": "https://api.github.com/repos/owner/repo/issues/123/comments",
        "events_url": "https://api.github.com/repos/owner/repo/issues/123/events",
        "html_url": "https://github.com/owner/repo/issues/123",
        "number": 123,
        "state": "open",
        "title": "Test Issue Title",
        "body": "Test issue content with detailed description",
        "user": {
            "login": "test-user",
            "id": 1,
            "node_id": "MDQ6VXNlcjE=",
            "avatar_url": "https://github.com/images/error/test_happy.gif",
            "url": "https://api.github.com/users/test-user",
            "html_url": "https://github.com/test-user",
            "type": "User",
            "site_admin": False,
        },
        "labels": [
            {
                "id": 1,
                "node_id": "MDU6TGFiZWwx",
                "url": "https://api.github.com/repos/owner/repo/labels/bug",
                "name": "bug",
                "color": "d73a4a",
                "default": True,
                "description": "Something isn't working",
            }
        ],
        "assignee": None,
        "assignees": [],
        "milestone": None,
        "locked": False,
        "active_lock_reason": None,
        "comments": 0,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "closed_at": None,
        "author_association": "OWNER",
        "state_reason": None,
    }


@pytest.fixture
def mock_pr_response() -> dict[str, Any]:
    return {
        "url": "https://api.github.com/repos/owner/repo/pulls/456",
        "id": 1,
        "node_id": "MDExOlB1bGxSZXF1ZXN0MQ==",
        "html_url": "https://github.com/owner/repo/pull/456",
        "diff_url": "https://github.com/owner/repo/pull/456.diff",
        "patch_url": "https://github.com/owner/repo/pull/456.patch",
        "issue_url": "https://api.github.com/repos/owner/repo/issues/456",
        "number": 456,
        "state": "open",
        "title": "Test PR Title",
        "user": {
            "login": "test-user",
            "id": 1,
            "type": "User",
            "site_admin": False,
        },
        "body": "Test PR description",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "closed_at": None,
        "merged_at": None,
        "merge_commit_sha": "abc123def456",
        "assignee": None,
        "assignees": [],
        "requested_reviewers": [],
        "requested_teams": [],
        "labels": [],
        "milestone": None,
        "draft": False,
        "commits_url": "https://api.github.com/repos/owner/repo/pulls/456/commits",
        "review_comments_url": "https://api.github.com/repos/owner/repo/pulls/456/comments",
        "review_comment_url": "https://api.github.com/repos/owner/repo/pulls/comments{/number}",
        "comments_url": "https://api.github.com/repos/owner/repo/issues/456/comments",
        "head": {
            "label": "owner:feature-branch",
            "ref": "feature-branch",
            "sha": "abc123def456",
        },
        "base": {
            "label": "owner:main",
            "ref": "main",
            "sha": "def456abc789",
        },
        "author_association": "OWNER",
        "auto_merge": None,
        "active_lock_reason": None,
    }


@pytest.fixture
def mock_issue_content(mock_issue_response: dict[str, Any]) -> str:
    return mock_issue_response["body"]


@pytest.fixture
def mock_pr_history(mock_pr_response: dict[str, Any]) -> str:
    return mock_pr_response["body"]


def test_get_latest_commit_id(
    mock_commit_response: dict[str, Any], mocker: MockerFixture
) -> None:
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = [mock_commit_response]
    mock_response.status_code = 200
    mocker.patch(
        "requests.request",
        return_value=mock_response,
    )

    result = get_latest_commit_id("https://github.com/owner/repo")
    assert result == "abc123def456"


@pytest.mark.parametrize(
    "content,expected_hash",
    [
        (
            "test content",
            "6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72",
        ),
        (
            pathlib.Path("test_file.txt"),
            "6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72",
        ),
    ],
)
def test_hash_content(
    content: str | pathlib.Path, expected_hash: str, mocker: MockerFixture
) -> None:
    if isinstance(content, pathlib.Path):
        mocker.patch.object(pathlib.Path, "read_text", return_value="test content")

    result = hash_content(content)
    assert result == expected_hash


def test_get_instructions() -> None:
    repo_url = "https://github.com/owner/repo"
    commit_id = "abc123def456"
    result = get_instructions(repo_url, commit_id)

    assert repo_url in result
    assert commit_id in result
    assert "clone" in result.lower()
    assert "checkout" in result.lower()
    assert "branch" in result.lower()


def test_create_sample(
    mock_issue_content: str,
    mock_pr_history: str,
    mocker: MockerFixture,
) -> None:
    repo_url = "https://github.com/owner/repo"
    commit_id = "abc123def456"
    repo_install_script = "install.sh"

    sample = create_sample(
        repo_url=repo_url,
        commit_id=commit_id,
        pr_history=mock_pr_history,
        repo_install_script=repo_install_script,
        issue_content=mock_issue_content,
    )

    assert isinstance(sample, Sample)
    assert sample.metadata is not None
    assert "owner" in sample.metadata
    assert "repo_name" in sample.metadata
    assert sample.metadata["commit_id"] == commit_id
    assert sample.files is not None
    assert "instructions.txt" in sample.files
    assert "issue_content.txt" in sample.files
    assert "pr_history.txt" in sample.files
    assert "repo_install_script.sh" in sample.files
    assert mock_issue_content in sample.files["issue_content.txt"]
    assert mock_pr_history in sample.files["pr_history.txt"]


@pytest.mark.parametrize(
    "live_pull_issue,issue_content,live_pull_prs,pr_history,should_raise",
    [
        (63, None, None, None, False),  # Only live_pull_issue
        (None, "content", None, None, False),  # Only issue_content
        (63, "content", None, None, True),  # Both live_pull_issue and issue_content
        (None, None, None, None, True),  # Neither live_pull_issue nor issue_number
        (63, None, [1, 2], None, False),  # live_pull_issue and live_pull_prs
        (63, None, None, "history", False),  # live_pull_issue and pr_history
        (63, None, [1, 2], "history", True),  # Both live_pull_prs and pr_history
    ],
)
def test_fix_repo_issue_validation(
    live_pull_issue: int | None,
    issue_content: str | None,
    live_pull_prs: list[int] | None,
    pr_history: str | None,
    should_raise: bool,
    mocker: MockerFixture,
    mock_issue_response: dict[str, Any],
    mock_pr_response: dict[str, Any],
    mock_commit_response: dict[str, Any],
) -> None:
    # Mock GitHub API responses
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = [mock_commit_response]
    mock_response.status_code = 200
    mocker.patch(
        "requests.request",
        return_value=mock_response,
    )
    mocker.patch(
        "fix_repo_issue.pull_git_content.get_issue_content",
        return_value=(mock_issue_response["body"], {"raw": "data"}),
    )
    mocker.patch(
        "fix_repo_issue.pull_git_content.get_pr_content",
        return_value=(mock_pr_response["body"], [{"raw": "data"}]),
    )

    if should_raise:
        with pytest.raises(ValueError):
            fix_repo_issue(
                live_pull_issue=live_pull_issue,
                issue_content=issue_content,
                live_pull_prs=live_pull_prs,
                pr_history=pr_history,
            )
    else:
        result = fix_repo_issue(
            live_pull_issue=live_pull_issue,
            issue_content=issue_content,
            live_pull_prs=live_pull_prs,
            pr_history=pr_history,
            issue_number=123 if not live_pull_issue else None,
        )
        assert isinstance(result, Task)


@pytest.mark.asyncio
async def test_pr_and_end_scorer(mocker: MockerFixture) -> None:
    # Mock sandbox exec
    mock_sandbox = mocker.MagicMock()
    mock_result = mocker.MagicMock()
    mock_result.returncode = 0
    mock_sandbox.exec = AsyncMock(return_value=mock_result)
    mocker.patch("inspect_ai.util.sandbox", return_value=mock_sandbox)

    # Mock GitHub API responses
    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "ref": "refs/heads/test",
        "object": {"sha": "abc123"},
    }
    mocker.patch(
        "requests.request",
        return_value=mock_response,
    )
    mocker.patch(
        "fix_repo_issue.end_run.remote_base_branch_exists",
        return_value=False,
    )
    mocker.patch("fix_repo_issue.end_run.create_remote_base_branch")
    mocker.patch(
        "fix_repo_issue.end_run.get_run_head_branch_name",
        return_value="head_branch",
    )
    mocker.patch(
        "fix_repo_issue.end_run.get_remote_base_branch_name",
        return_value="base_branch",
    )

    # Mock PR body file
    mocker.patch("builtins.open", mocker.mock_open(read_data="Test PR body"))

    # Create and run scorer
    scorer = pr_and_end("owner/repo", 123, "abc123def456", "origin")
    state = TaskState(
        model=ModelName("openai/gpt-4"),
        messages=[],
        sample_id="test",
        epoch=1,
        input="test",
    )
    state.store.set("sandbox", mock_sandbox)  # Set sandbox in the store

    # Set up sandbox context
    from inspect_ai.util._sandbox.context import sandbox_environments_context_var

    token = sandbox_environments_context_var.set({"default": mock_sandbox})
    try:
        target = mocker.MagicMock()
        score = await scorer(state, target)
        assert score.value == 1
    finally:
        sandbox_environments_context_var.reset(token)
