# Handles turning issue data into formatted string content for files given to the agent
import argparse
import json
import pathlib

from src import task_schema


def clean_up_comments(comments: list[dict]) -> str:
    if not comments:
        return "No comments"

    cleaned = []
    for comment in comments:
        author = comment["author"]["login"]
        body = comment["body"].replace("\r\n", "\n").strip()  # Normalize line endings
        date = comment["createdAt"].split("T")[0]  # Get just the date part
        cleaned.append(f"[{date}] {author}: {body}")

    return "\n\n".join(cleaned)


def format_issue_data(in_data: dict | task_schema.GitHubIssueResponse) -> str:
    """Create a summary of a GitHub issue from GraphQL response data."""
    data = in_data.model_dump() if isinstance(in_data, task_schema.GitHubIssueResponse) else in_data
    issue = data["data"]["repository"]["issue"]
    labels = (
        [label["name"] for label in issue["labels"]["nodes"]] if "nodes" in issue["labels"] else []
    )
    comments = issue["comments"]["nodes"]
    clean_comments = clean_up_comments(comments)
    msg = f"Title: {issue['title']}\n"
    msg += f"Author: {issue['author']['login']}\n"
    msg += f"Created at: {issue['createdAt']}\n"
    msg += f"Body: {issue['body']}\n"
    msg += f"Labels: {labels}\n"
    msg += f"Comments: {clean_comments}"
    return msg


if __name__ == "__main__":
    args = argparse.ArgumentParser()
    args.add_argument("--data-file", type=str, required=True)
    args.add_argument("--output-dir", type=str, required=True)
    args = args.parse_args()

    with open(args.data_file, "r") as f:
        data = json.load(f)

    formatted_issue_data = format_issue_data(data)

    file_name = f"formatted_{args.data_file}"
    output_path = pathlib.Path(args.output_dir) / file_name
    output_path = output_path.with_suffix(".txt")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(formatted_issue_data)
