import json

import pytest
import requests
from pytest_mock import MockerFixture

from ..pull_git_content import get_issue_content, get_pr_content, get_pr_data


@pytest.fixture
def mock_issue_response() -> dict:
    return {
        "number": 123,
        "title": "Test Issue",
        "body": "This is a test issue",
        "state": "open",
    }


@pytest.fixture
def mock_pr_response() -> dict:
    return {
        "number": 456,
        "title": "Test PR",
        "body": "This is a test PR",
        "state": "open",
        "head": {"ref": "feature-branch"},
    }


@pytest.fixture
def mock_comments_response() -> list:
    return [
        {"id": 1, "body": "Test comment 1"},
        {"id": 2, "body": "Test comment 2"},
    ]


@pytest.fixture
def mock_review_comments_response() -> list:
    return [
        {"id": 3, "body": "Test review comment 1"},
        {"id": 4, "body": "Test review comment 2"},
    ]


def test_get_issue_content(mock_issue_response: dict, mocker: MockerFixture) -> None:
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = mock_issue_response
    mock_response.raise_for_status.return_value = None

    mocker.patch("requests.get", return_value=mock_response)
    result = get_issue_content("owner/repo", 123)
    assert result == json.dumps(mock_issue_response)


@pytest.mark.parametrize(
    "status_codes,expected",
    [
        ([200, 200, 200], True),  # All requests succeed
        ([404, 200, 200], False),  # PR request fails
        ([200, 404, 200], False),  # Comments request fails
        ([200, 200, 404], False),  # Review comments request fails
    ],
)
def test_get_pr_data_error_handling(
    status_codes: list[int],
    expected: bool,
    mock_pr_response: dict,
    mock_comments_response: list,
    mock_review_comments_response: list,
    mocker: MockerFixture,
) -> None:
    responses = []
    for status_code in status_codes:
        mock_response = mocker.MagicMock()
        if status_code == 200:
            mock_response.raise_for_status.return_value = None
        else:
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError()
        responses.append(mock_response)

    responses[0].json.return_value = mock_pr_response
    responses[1].json.return_value = mock_comments_response
    responses[2].json.return_value = mock_review_comments_response

    mocker.patch("requests.get", side_effect=responses)
    result = get_pr_data("owner/repo", 456)
    if expected:
        assert result == {
            "pr": mock_pr_response,
            "comments": mock_comments_response,
            "review_comments": mock_review_comments_response,
        }
    else:
        assert result == {}


def test_get_pr_content(
    mock_pr_response: dict,
    mock_comments_response: list,
    mock_review_comments_response: list,
    mocker: MockerFixture,
) -> None:
    mock_response = mocker.MagicMock()
    mock_response.json.side_effect = [
        mock_pr_response,
        mock_comments_response,
        mock_review_comments_response,
    ]
    mock_response.raise_for_status.return_value = None

    expected_data = [
        {
            "pr": mock_pr_response,
            "comments": mock_comments_response,
            "review_comments": mock_review_comments_response,
        }
    ]

    mocker.patch("requests.get", return_value=mock_response)
    result = get_pr_content("owner/repo", [456])
    assert result == json.dumps(expected_data)
