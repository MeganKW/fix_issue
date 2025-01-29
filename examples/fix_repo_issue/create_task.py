import argparse
import datetime as dt
import pathlib
from datetime import datetime

import src.get_issue_or_pr_data as get_issue_or_pr_data
import src.task_schema as task_schema

DEFAULT_TASK_JSONL_FILE = pathlib.Path("tasks.jsonl")


def create_task(
    working_repo_url: str,
    issue_to_fix: int,
    starting_commit: str,
    target_remote: str,
    live_pull_issues: list[int],
    live_pull_prs: list[int],
    source_urls: list[str],
    ci_available_mid_run: bool,
    task_alias: str | None,
    repo_install_script: str | None,
) -> task_schema.TaskData:
    task_id = make_task_id(working_repo_url, issue_to_fix, starting_commit)
    issue_data_list = []
    pr_data_list = []

    owner, repo = working_repo_url.split("/")[-2:]

    if not source_urls:
        source_urls = [f"{working_repo_url}/issues/{issue_to_fix}"]

    for url in source_urls:
        issue_or_pr, curr_owner, curr_repo, number = get_issue_or_pr_data.parse_url(url)

        if issue_or_pr == "issue":
            issue_data = get_issue_or_pr_data.get_issue_data(owner, repo, number, max_num=100)
            # Validate the issue data
            issue_response = task_schema.GitHubIssueResponse.model_validate(issue_data)
            issue_data_list.append(issue_response)
        else:
            pr_data = get_issue_or_pr_data.get_pr_data(owner, repo, number, max_num=100)
            # Validate the PR data
            pr_response = task_schema.GitHubPRResponse.model_validate(pr_data)
            pr_data_list.append(pr_response)

    metadata = task_schema.TaskMetadata(
        datetime_sourced=datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        source_urls=source_urls,
        source_issues=[issue_data.data.repository.issue.number for issue_data in issue_data_list],
        source_prs=[pr_data.data.repository.pullRequest.number for pr_data in pr_data_list],
        ci_available_mid_run=ci_available_mid_run,
        task_alias=task_alias,
    )

    task = task_schema.TaskData(
        task_id=task_id,
        working_repo_url=working_repo_url,
        starting_commit=starting_commit,
        issue_to_fix=issue_to_fix,
        target_remote=target_remote,
        pr_data=pr_data_list,
        issue_data=issue_data_list,
        live_pull_issues=live_pull_issues,
        live_pull_prs=live_pull_prs,
        repo_install_script=repo_install_script,
        metadata=metadata,
    )

    return task


def make_task_id(working_repo_url: str, issue_to_fix: int, commit_id: str) -> str:
    owner, repo = working_repo_url.split("/")[-2:]
    short_commit_id = commit_id[-5:]
    datetime_sourced = datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"fix_issue/{owner}/{repo}/issue_{issue_to_fix}/{short_commit_id}/{datetime_sourced}"


def main(args: argparse.Namespace) -> None:
    task = create_task(
        args.working_repo_url,
        args.issue_to_fix,
        args.starting_commit,
        args.target_remote,
        args.live_pull_issues,
        args.live_pull_prs,
        args.source_urls,
        args.ci_available_mid_run,
        args.task_alias,
        args.repo_install_script,
    )
    filename = f"{task.task_id.replace('/', '_')}.json"
    if args.output_json_file:
        with open(filename, "w") as f:
            f.write(task.model_dump_json())

    if args.add_to_jsonl_file:
        with open(DEFAULT_TASK_JSONL_FILE, "a") as f:
            f.write(task.model_dump_json())
            f.write("\n")

    print(f"\nTask created: {task.task_id}")
    print(f"Task data:\n{task.model_dump_json(indent=2)}")
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--working-repo-url",
        type=str,
        required=True,
        help="The URL of the repository to work on",
    )
    parser.add_argument(
        "--issue-to-fix", type=int, required=True, help="The number of the issue to fix"
    )
    parser.add_argument(
        "--starting-commit",
        type=str,
        required=True,
        help="The commit ID to start from",
    )
    parser.add_argument(
        "--target-remote",
        type=str,
        required=False,
        default="origin",
        help="The remote of the repo the PR to be pushed to. Defaults to 'origin'",
    )
    parser.add_argument(
        "--live-pull-issues",
        type=int,
        nargs="*",
        required=False,
        default=[],
        help="List of issue numbers to pull live during execution",
    )
    parser.add_argument(
        "--live-pull-prs",
        type=int,
        nargs="*",
        required=False,
        default=[],
        help="List of PR numbers to pull live during execution",
    )
    parser.add_argument(
        "--source-urls",
        type=str,
        required=False,
        nargs="+",
        help="A list of issue or pull urls for giving to the agent.\
        If this argument is not provided the only source url will be the \
        url for the provided issue number on the working repo url",
    )
    parser.add_argument(
        "--ci-available-mid-run",
        type=lambda x: x.lower() in ("true", "True"),
        required=True,
        help="Whether CI is available mid-run",
    )
    parser.add_argument(
        "--task-alias", type=str, required=False, help="An optional alias for the task"
    )
    parser.add_argument(
        "--repo-install-script",
        type=str,
        required=False,
        help="An optional script to do installation of the repo after it has been cloned",
    )
    parser.add_argument(
        "--output-json-file",
        type=bool,
        required=False,
        default=False,
        help="Whether to output the task to a single JSON file",
    )
    parser.add_argument(
        "--add-to-jsonl-file",
        type=bool,
        required=False,
        default=False,
        help="Whether to add the task to the JSONL file",
    )
    args = parser.parse_args()
    main(args)
