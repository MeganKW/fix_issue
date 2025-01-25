import argparse
import json
import pathlib

import git

from .shared import RUN_METADATA_FILE, get_repo_path_from_url, get_short_commit_id

AGENT_PR_CONTENT_OUTPUT_FILE = pathlib.Path("pr_content.md")


def read_pr_content_from_agent(agent_pr_content_file: pathlib.Path) -> dict:
    with open(agent_pr_content_file, "r") as f:
        return json.load(f)


def make_pr_body_content(agent_pr_content: dict) -> str:
    # TODO
    return ""


def read_run_metadata() -> dict:
    with open(RUN_METADATA_FILE, "r") as f:
        return json.load(f)


def finalize(
    repo_url: str,
    issue_number: int,
    remote_name: str = "origin",
):
    run_metadata = read_run_metadata()
    run_uuid = run_metadata["run_uuid"]

    repo_path = get_repo_path_from_url(repo_url)
    repo = git.Repo(repo_path)

    short_commit_id = get_short_commit_id(run_metadata["commit_id"])
    branch_name = f"fix/{issue_number}/source_{short_commit_id}/{run_uuid}"
    repo.remote(remote_name).push(branch_name)

    agent_pr_content = read_pr_content_from_agent(AGENT_PR_CONTENT_OUTPUT_FILE)

    # Augment the PR content with human friendly content (like how to access the transcript of the run)
    pr_content = make_pr_body_content(agent_pr_content)

    # Make a PR from the branch fix/<issue_number>/source_<short_commit_id>/<uuid v4> to the branch fix/<issue_number>/source_<short_commit_id>
    repo.create_pull(
        title=f"Fix {issue_number} - run {run_uuid}",
        body=pr_content,
        head=branch_name,
        base=f"fix/{issue_number}/source_{short_commit_id}",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo_url", type=str, required=True)
    parser.add_argument("--issue_number", type=int, required=True)
    parser.add_argument("--remote_name", type=str, default="origin")
    args = parser.parse_args()

    finalize(
        repo_url=args.repo_url,
        issue_number=args.issue_number,
        remote_name=args.remote_name,
    )


if __name__ == "__main__":
    main()
