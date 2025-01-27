import datetime
import json
import os

import requests


def make_request_to_github(
    method: str, repo_url: str, endpoint: str, payload: dict | None = None
) -> requests.Response:
    owner, repo_name = repo_url.split("/")[-2:]

    github_token = os.getenv("GITHUB_TOKEN")
    assert github_token is not None

    url = f"https://api.github.com/repos/{owner}/{repo_name}/{endpoint}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {github_token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
    response = requests.request(method, url, headers=headers, json=payload)
    raw_curl = f"curl -X {method} -H 'Accept: application/vnd.github+json' -H 'Authorization: Bearer {github_token}' -H 'X-GitHub-Api-Version: 2022-11-28' -H 'Content-Type: application/json' {url} {f'-d {json.dumps(payload)}' if payload else ''}"
    print("\n" + raw_curl + "\n")
    response.raise_for_status()
    return response


def get_short_commit_id(commit_id: str) -> str:
    return commit_id[:5]


def get_remote_base_branch_name(issue_number: int, commit_id: str) -> str:
    return f"issue_{issue_number}/commit_{get_short_commit_id(commit_id)}"


def get_run_head_branch_name(run_uuid: str) -> str:
    datetime_str = datetime.datetime.now().strftime("%M-%H-%d-%m-%Y")
    return f"date_{datetime_str}-run_{run_uuid}"


def remote_base_branch_exists(repo_url: str, issue_number: int, commit_id: str) -> bool:
    branch = get_remote_base_branch_name(issue_number, commit_id)
    try:
        make_request_to_github("GET", repo_url, f"branches/{branch}")
    except requests.exceptions.HTTPError:
        return False
    return True


def create_remote_base_branch(repo_url: str, issue_number: int, commit_id: str) -> None:
    branch = get_remote_base_branch_name(issue_number, commit_id)
    print(f"Creating source branch for commit {commit_id}")
    make_request_to_github(
        "POST",
        repo_url,
        "git/refs",
        {
            "ref": f"refs/heads/{branch}",
            "sha": commit_id,
        },
    )
