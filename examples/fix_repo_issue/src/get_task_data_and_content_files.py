# Takes a URL and outputs the formatted content of the issue or PR to a file
# This is a simple wrapper around get_issue_or_pr_data and the format scripts,
# format_issue_content and format_pr_content
import argparse
import json
import pathlib

from src import format_issue_content, format_pr_content, get_issue_or_pr_data


def main(args: argparse.Namespace) -> None:
    for url in args.urls:
        owner: str
        repo: str
        issue_or_pr: str
        number: int
        issue_or_pr, owner, repo, number = get_issue_or_pr_data.parse_url(url)

        output_dir = pathlib.Path(args.output_dir)

        if issue_or_pr == "issue":
            issue_data = get_issue_or_pr_data.get_issue_data(owner, repo, number, args.max_num)
            issue_content = format_issue_content.format_issue_data(issue_data)
            data_file_name = get_issue_or_pr_data.get_data_file_name("issue", owner, repo, number)
            output_dir.mkdir(parents=True, exist_ok=True)

            data_file_path = output_dir / data_file_name
            with open(data_file_path, "w") as f:
                json.dump(issue_data, f, indent=2)

            content_file_path = data_file_path.with_suffix(".txt")
            with open(content_file_path, "w") as f:
                f.write(issue_content)
        else:
            pr_data = get_issue_or_pr_data.get_pr_data(owner, repo, number, args.max_num)
            pr_content = format_pr_content.format_pr_data(pr_data)
            output_dir.mkdir(parents=True, exist_ok=True)

            data_file_name = get_issue_or_pr_data.get_data_file_name("pr", owner, repo, number)
            data_file_path = output_dir / data_file_name
            with open(data_file_path, "w") as f:
                json.dump(pr_data, f, indent=2)

            content_file_path = data_file_path.with_suffix(".txt")
            with open(content_file_path, "w") as f:
                f.write(pr_content)


if __name__ == "__main__":
    args = argparse.ArgumentParser()
    # Can accept a list of multiple URLs
    args.add_argument("--urls", type=str, nargs="+", required=True)
    args.add_argument("--output-dir", type=str, required=True)
    args.add_argument("--max-num", type=int, default=100, help="Maximum number of nodes to fetch")
    args = args.parse_args()
    main(args)
