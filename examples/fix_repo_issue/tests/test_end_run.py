import datetime

import pytest
import requests
from fix_repo_issue.end_run import (
    create_remote_base_branch,
    get_remote_base_branch_name,
    get_run_head_branch_name,
    get_short_commit_id,
    make_request_to_github,
    remote_base_branch_exists,
)
from pytest_mock import MockerFixture


@pytest.mark.parametrize(
    "method,repo_url,endpoint,payload,expected_url",
    [
        (
            "GET",
            "owner/repo",
            "branches/main",
            None,
            "https://api.github.com/repos/owner/repo/branches/main",
        ),
        (
            "POST",
            "owner/repo",
            "git/refs",
            {"ref": "refs/heads/branch", "sha": "abc123"},
            "https://api.github.com/repos/owner/repo/git/refs",
        ),
    ],
)
def test_make_request_to_github(
    method: str,
    repo_url: str,
    endpoint: str,
    payload: dict | None,
    expected_url: str,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
) -> None:
    mock_response = mocker.MagicMock()
    mock_response.raise_for_status.return_value = None

    def mock_request(
        method: str, url: str, headers: dict, json: dict | None
    ) -> pytest.MonkeyPatch:
        assert url == expected_url
        assert headers["Authorization"] == "Bearer test_token"
        assert headers["Accept"] == "application/vnd.github+json"
        if payload:
            assert json == payload
        return mock_response

    monkeypatch.setenv("GITHUB_TOKEN", "test_token")
    mocker.patch("requests.request", mock_request)
    response = make_request_to_github(method, repo_url, endpoint, payload)
    assert response == mock_response


@pytest.mark.parametrize(
    "commit_id,expected",
    [
        ("abcdef1234567890", "abcde"),
        ("123456789", "12345"),
    ],
)
def test_get_short_commit_id(commit_id: str, expected: str) -> None:
    assert get_short_commit_id(commit_id) == expected


@pytest.mark.parametrize(
    "issue_number,commit_id,expected",
    [
        (123, "abcdef1234567890", "issue_123/commit_abcde"),
        (456, "123456789", "issue_456/commit_12345"),
    ],
)
def test_get_remote_base_branch_name(
    issue_number: int, commit_id: str, expected: str
) -> None:
    assert get_remote_base_branch_name(issue_number, commit_id) == expected


def test_get_run_head_branch_name(mocker: MockerFixture) -> None:
    run_uuid = "test_uuid"
    mock_dt = datetime.datetime(2024, 1, 1, 12, 30)
    mocker.patch("datetime.datetime", autospec=True).now.return_value = mock_dt
    result = get_run_head_branch_name(run_uuid)
    assert result == "date_30-12-01-01-2024-run_test_uuid"


@pytest.mark.parametrize(
    "status_code,expected_exists",
    [
        (200, True),
        (404, False),
    ],
)
def test_remote_base_branch_exists(
    status_code: int,
    expected_exists: bool,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
) -> None:
    mock_response = mocker.MagicMock()
    mock_response.raise_for_status.side_effect = (
        None if status_code == 200 else requests.exceptions.HTTPError()
    )

    monkeypatch.setenv("GITHUB_TOKEN", "test_token")
    mock_request = mocker.patch("requests.request", return_value=mock_response)
    exists = remote_base_branch_exists("owner/repo", 123, "abcdef1234567890")
    assert exists == expected_exists


def test_create_remote_base_branch(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    mock_response = mocker.MagicMock()
    mock_response.raise_for_status.return_value = None

    monkeypatch.setenv("GITHUB_TOKEN", "test_token")
    mock_request = mocker.patch("requests.request", return_value=mock_response)
    create_remote_base_branch("owner/repo", 123, "abcdef1234567890")
    mock_request.assert_called_once()
    _, kwargs = mock_request.call_args
    assert kwargs["json"] == {
        "ref": "refs/heads/issue_123/commit_abcde",
        "sha": "abcdef1234567890",
    }
