import json
from pathlib import Path

import pytest
from fix_repo_issue.src.display_pr_content import (
    format_comment,
    format_pr_data,
    format_review,
    format_review_comment,
    is_review,
)

TEST_DATA_DIR = Path(__file__).parent / "test_responses"


@pytest.fixture
def pr_data():
    with open(TEST_DATA_DIR / "pr_1161_graph_ql_response_raw.json") as f:
        return json.load(f)


def test_is_review():
    """Test review detection function."""
    assert is_review({"bodyText": "some text"}) is True
    assert is_review({"body": "some text"}) is False


@pytest.mark.parametrize(
    "expected_content",
    [
        "Title: Add Goodfire API Provider Support",
        "# Add Goodfire API Provider Support",
        "## Overview",
        "This PR introduces support for the [Goodfire API]",
    ],
)
def test_format_pr_data_basic_content(pr_data, expected_content):
    """Test that basic PR content (title, body) is included in formatted output."""
    formatted = format_pr_data(pr_data)
    assert expected_content in formatted


@pytest.mark.parametrize(
    "expected_content",
    [
        "Fantastic! So happy to see this and excited to see it built out further",
        "jjallaire:",
    ],
)
def test_format_pr_data_review_content(pr_data, expected_content):
    """Test that review content is properly formatted."""
    formatted = format_pr_data(pr_data)
    assert expected_content in formatted


@pytest.mark.parametrize(
    "expected_content",
    [
        "These we want to implement as `model_args`",  # Comment content
        "Code context:",  # Review formatting
        "==========================================",  # Diff formatting
        "+@modelapi",  # Part of a diff hunk we know exists
        "jjallaire:",  # Author name
    ],
)
def test_format_pr_data_review_comments(pr_data, expected_content):
    """Test that review comments are properly formatted."""
    formatted = format_pr_data(pr_data)
    assert expected_content in formatted


def test_format_review_comment():
    """Test formatting of individual review comments."""
    comment_data = {
        "author": {"login": "testuser"},
        "body": "Test comment",
        "createdAt": "2025-01-20T23:32:23Z",
        "diffHunk": "@@ -1,1 +1,1 @@\n-old\n+new",
        "position": 1,
        "subjectType": "LINE",
    }

    formatted = format_review_comment(comment_data)
    assert "testuser:" in formatted
    assert "Test comment" in formatted
    assert "@@ -1,1 +1,1 @@" in formatted


def test_format_comment():
    """Test formatting of regular comments."""
    comment_data = {
        "author": {"login": "testuser"},
        "body": "Test comment",
        "createdAt": "2025-01-20T23:32:23Z",
    }

    formatted = format_comment(comment_data)
    assert "testuser:" in formatted
    assert "Test comment" in formatted
    assert "[2025-01-20T23:32:23Z]" in formatted


def test_format_review():
    """Test formatting of complete reviews."""
    review_data = {
        "bodyText": "Main review comment",
        "createdAt": "2025-01-20T23:32:23Z",
        "author": {"login": "reviewer"},
        "comments": {
            "nodes": [
                {
                    "author": {"login": "reviewer"},
                    "body": "Inline comment",
                    "createdAt": "2025-01-20T23:32:23Z",
                    "diffHunk": "@@ -1,1 +1,1 @@\n-old\n+new",
                    "position": 1,
                    "subjectType": "LINE",
                }
            ]
        },
    }

    formatted = format_review(review_data)
    assert "reviewer:" in formatted
    assert "Main review comment" in formatted
    assert "Inline comment" in formatted
    assert "@@ -1,1 +1,1 @@" in formatted
