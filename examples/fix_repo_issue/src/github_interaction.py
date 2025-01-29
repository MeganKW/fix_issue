import datetime
import json

import requests

LABELS = {
    "agent": {"name": "agent", "color": "black"},
    "no_pr_body_file": {"name": "no_pr_body_file", "color": "yellow"},
}


def get_short_commit_id(commit_id: str) -> str:
    return commit_id[:5]


def get_remote_base_branch_name(issue_number: int, commit_id: str) -> str:
    return f"issue_{issue_number}/commit_{get_short_commit_id(commit_id)}"


def get_run_head_branch_name(run_uuid: str) -> str:
    datetime_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    return f"agent-name_date-{datetime_str}_run-{run_uuid}"


def _create_label_if_not_exists(
    repo_url: str, label_name: str, label_color: str, github_token: str
) -> None:
    label_dict = {"name": label_name, "color": label_color}
    try:
        _ = make_request_to_github("POST", repo_url, "labels", github_token, label_dict)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 422:  # Label already exists
            return None
        else:
            raise e


def create_labels_if_not_exists(repo_url: str, github_token: str) -> None:
    for label in LABELS.values():
        _create_label_if_not_exists(repo_url, label["name"], label["color"], github_token)


def make_request_to_github(
    method: str,
    repo_url: str,
    endpoint: str,
    github_token: str,
    payload: dict | None = None,
    quiet: bool = True,
) -> requests.Response:
    """Simple wrapper for making requests to github REST API via curl.
    If quiet is False, will print the curl command and the response json."""
    owner, repo_name = repo_url.split("/")[-2:]

    url = f"https://api.github.com/repos/{owner}/{repo_name}/{endpoint}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {github_token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
    response = requests.request(method, url, headers=headers, json=payload)

    # For easier debugging
    raw_curl = f"""curl -X {method} -H 'Accept: application/vnd.github+json' \
        -H 'Authorization: Bearer {github_token}' \
        -H 'X-GitHub-Api-Version: 2022-11-28' \
        -H 'Content-Type: application/json' \
        {url} {f'-d {json.dumps(payload)}' if payload else ''}"""

    if not quiet:  # Yeah yeah, logging exists but who cares
        print("\n" + raw_curl + "\n")
        print(response.json())

    response.raise_for_status()
    return response


def remote_base_branch_exists(
    repo_url: str,
    issue_number: int,
    commit_id: str,
    github_token: str,
) -> bool:
    branch = get_remote_base_branch_name(issue_number, commit_id)
    try:
        make_request_to_github("GET", repo_url, f"branches/{branch}", github_token)
    except requests.exceptions.HTTPError:
        return False
    return True


def create_remote_base_branch(
    repo_url: str,
    issue_number: int,
    commit_id: str,
    github_token: str,
) -> None:
    branch = get_remote_base_branch_name(issue_number, commit_id)
    print(f"Creating source branch for commit {commit_id}")
    make_request_to_github(
        "POST",
        repo_url,
        "git/refs",
        github_token,
        {
            "ref": f"refs/heads/{branch}",
            "sha": commit_id,
        },
    )
