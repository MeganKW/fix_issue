# Handles turning pr data into formatted string content for files given to the agent
import argparse
import json
import pathlib
import textwrap

from src import task_schema


def is_review(data: dict) -> bool:
    if "bodyText" in data:
        return True
    return False


def format_review(review: dict) -> str:
    """Processes review objects into a formatted string."""
    review_comments = review["comments"]["nodes"]
    formatted_review_comments = []
    # Sort by created at
    review_comments.sort(key=lambda x: x["createdAt"])
    for review_comment in review_comments:
        formatted_review_comments.append(format_review_comment(review_comment))

    msg = f"""[{review['createdAt']}] REVIEW
{review['author']['login']}:
{review['bodyText']}
    """
    for comment in formatted_review_comments:
        msg += textwrap.indent(comment, "       ") + "\n\n"
    return msg


def format_review_comment(review_comment_data: dict) -> str:
    """Processes review comments (comments with diffs) into a formatted string."""
    if review_comment_data["subjectType"] == "LINE":
        code_context = (
            "==========================================\n"
            + "\n".join(review_comment_data["diffHunk"].split("\n")[-4:])
            + "\n=========================================="
        )
    else:
        code_context = (
            "==========================================\n"
            + review_comment_data["diffHunk"]
            + "\n=========================================="
        )
    maybe_outdated = "[OUTDATED]" if review_comment_data["position"] is None else ""
    msg = f"""[{review_comment_data['createdAt']}]{maybe_outdated}
Code context:
{code_context}
{review_comment_data["author"]["login"]}:
{review_comment_data["body"]}
    """
    return msg


def format_comment(comment: dict) -> str:
    """Processes comment objects into a formatted string."""
    msg = f"""[{comment['createdAt']}]
{comment['author']['login']}:
{comment['body']}
    """
    return msg


def format_pr_data(pr_github_response: task_schema.GitHubPRResponse | dict) -> str:
    pr_response = dict(pr_github_response)
    pr_data = pr_response["data"]["repository"]["pullRequest"]
    title = pr_data["title"]
    body = pr_data["body"]
    author = pr_data["author"]["login"]
    created_at = pr_data["createdAt"]

    comments: list[dict] = pr_data["comments"]["nodes"]

    reviews: list[dict] = pr_data["reviews"]["nodes"]
    reviews.sort(key=lambda x: x["createdAt"])
    reviews_and_comments = reviews + comments
    reviews_and_comments.sort(key=lambda x: x["createdAt"])
    formatted_reviews_and_comments = []

    for obj in reviews_and_comments:
        if is_review(obj):
            formatted_reviews_and_comments.append(format_review(obj))
        else:
            formatted_reviews_and_comments.append(format_comment(obj))

    msg = f"Title: {title}\n"
    msg += f"PR #{pr_data['number']}\n"
    msg += f"Author: {author}\n"
    msg += f"Created at: {created_at}\n"
    msg += f"Body: {body}\n"
    msg += "Comments:\n"
    for comment in formatted_reviews_and_comments:
        msg += comment + "\n\n"
    return msg


if __name__ == "__main__":
    args = argparse.ArgumentParser()
    args.add_argument("--data-file", type=str, required=True)
    args.add_argument("--output-dir", type=str, required=True)
    args = args.parse_args()

    with open(args.data_file, "r") as f:
        data = json.load(f)

    formatted_pr_data = format_pr_data(data)

    file_name = f"formatted_{args.data_file}"
    output_path = pathlib.Path(args.output_dir) / file_name
    output_path = output_path.with_suffix(".txt")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(formatted_pr_data)
