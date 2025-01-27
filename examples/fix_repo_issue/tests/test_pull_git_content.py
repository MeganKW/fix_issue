import json
import os

import pytest
import requests
from pytest_mock import MockerFixture

from fix_repo_issue.src.pull_git_content import (
    get_issue_content,
    get_pr_content,
    get_pr_data,
)


@pytest.fixture
def mock_issue_response() -> dict:
    return {
        "number": 123,
        "title": "Test Issue",
        "body": "This is a test issue",
        "state": "open",
    }


@pytest.fixture
def mock_issue_labels_response() -> list[dict]:
    return [
        {"name": "bug", "color": "red"},
        {"name": "enhancement", "color": "blue"},
    ]


@pytest.fixture
def mock_issue_comments_response() -> list[dict]:
    return [
        {
            "user": {"login": "user1"},
            "body": "Comment 1",
            "created_at": "2024-01-01T00:00:00Z",
        },
        {
            "user": {"login": "user2"},
            "body": "Comment 2",
            "created_at": "2024-01-02T00:00:00Z",
        },
    ]


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
def mock_comments_response() -> list[dict]:
    return [
        {"id": 1, "body": "Test comment 1"},
        {"id": 2, "body": "Test comment 2"},
    ]


@pytest.fixture
def mock_review_comments_response() -> list[dict]:
    return [
        {"id": 3, "body": "Test review comment 1"},
        {"id": 4, "body": "Test review comment 2"},
    ]


@pytest.fixture
def mock_graph_ql_response() -> dict:
    return {
        "data": {
            "repository": {
                "pullRequest": {
                    "title": "Test PR",
                    "body": "Test body",
                    "reviews": {"nodes": []},
                    "comments": {"nodes": [], "totalCount": 0},
                }
            }
        }
    }


def test_get_issue_content(
    mock_issue_response: dict,
    mock_issue_labels_response: list[dict],
    mock_issue_comments_response: list[dict],
    mocker: MockerFixture,
) -> None:
    def mock_get(url: str, *args: tuple, **kwargs: dict) -> requests.Response:
        mock_response = mocker.MagicMock(spec=requests.Response)
        if "/labels" in url:
            mock_response.json.return_value = mock_issue_labels_response
        elif "/comments" in url:
            mock_response.json.return_value = mock_issue_comments_response
        else:
            mock_response.json.return_value = mock_issue_response
        mock_response.status_code = 200
        return mock_response

    mocker.patch("requests.get", side_effect=mock_get)
    result, raw_data = get_issue_content("owner/repo", 123)
    assert isinstance(result, str)
    assert isinstance(raw_data, dict)
    assert raw_data == {
        "issue_labels_response": mock_issue_labels_response,
        "issue_comments_response": mock_issue_comments_response,
        "issue_info_response": mock_issue_response,
    }


@pytest.mark.parametrize(
    "status_codes,expected_empty",
    [
        ([200, 200, 200, 200], False),  # All requests succeed
        ([404, 200, 200, 200], True),  # PR request fails
        ([200, 404, 200, 200], True),  # Comments request fails
        ([200, 200, 404, 200], True),  # Review comments request fails
        ([200, 200, 200, 404], True),  # GraphQL request fails
    ],
)
def test_get_pr_data_error_handling(
    status_codes: list[int],
    expected_empty: bool,
    mock_pr_response: dict,
    mock_comments_response: list,
    mock_review_comments_response: list,
    mock_graph_ql_response: dict,
    mocker: MockerFixture,
) -> None:
    responses = []
    for status_code in status_codes[:-1]:  # Handle REST responses
        mock_response = mocker.MagicMock()
        if status_code == 200:
            mock_response.raise_for_status.return_value = None
        else:
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError()
        responses.append(mock_response)

    responses[0].json.return_value = mock_pr_response
    responses[1].json.return_value = mock_comments_response
    responses[2].json.return_value = mock_review_comments_response

    # Mock GraphQL response separately
    mock_graphql = mocker.MagicMock()
    mock_graphql.ok = status_codes[-1] == 200
    if mock_graphql.ok:
        mock_graphql.json.return_value = mock_graph_ql_response
    else:
        mock_graphql.json.side_effect = requests.exceptions.HTTPError()

    mocker.patch("requests.get", side_effect=responses)
    mocker.patch("requests.post", return_value=mock_graphql)
    mocker.patch.dict(os.environ, {"GITHUB_TOKEN": "dummy_token"})

    pr_data, raw_data = get_pr_data("owner/repo", 456)
    if expected_empty:
        assert pr_data == {}
        assert raw_data == {}
    else:
        assert pr_data == {
            "pr": mock_pr_response,
            "comments": mock_comments_response,
            "review_comments": mock_review_comments_response,
            "graph_ql_response": mock_graph_ql_response,
        }
        assert raw_data == pr_data


def test_get_pr_content(
    mock_pr_response: dict,
    mock_comments_response: list,
    mock_review_comments_response: list,
    mock_graph_ql_response: dict,
    mocker: MockerFixture,
) -> None:
    # Create separate mock responses for each request
    mock_pr = mocker.MagicMock()
    mock_pr.json.return_value = mock_pr_response
    mock_pr.raise_for_status.return_value = None

    mock_comments = mocker.MagicMock()
    mock_comments.json.return_value = mock_comments_response
    mock_comments.raise_for_status.return_value = None

    mock_review = mocker.MagicMock()
    mock_review.json.return_value = mock_review_comments_response
    mock_review.raise_for_status.return_value = None

    mock_responses = [mock_pr, mock_comments, mock_review]
    mock_get = mocker.MagicMock(side_effect=mock_responses)

    mock_graphql = mocker.MagicMock()
    mock_graphql.ok = True
    mock_graphql.json.return_value = mock_graph_ql_response

    mocker.patch("requests.get", side_effect=mock_get)
    mocker.patch("requests.post", return_value=mock_graphql)
    mocker.patch.dict(os.environ, {"GITHUB_TOKEN": "dummy_token"})

    expected_data = {
        "pr": mock_pr_response,
        "comments": mock_comments_response,
        "review_comments": mock_review_comments_response,
        "graph_ql_response": mock_graph_ql_response,
    }

    content, raw_data = get_pr_content("owner/repo", [456])
    assert isinstance(content, str)
    parsed_content = json.loads(content)
    assert len(parsed_content) == 1
    assert raw_data == [expected_data]
