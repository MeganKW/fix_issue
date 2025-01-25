import argparse
import json
import os
import pathlib
import uuid

import github
import github.Repository
import requests

HOME_DIR = pathlib.Path("examples/fix_repo_issue/test_env")
SHORT_COMMIT_ID_LENGTH = 6
RUN_METADATA_FILE = pathlib.Path(".run_metadata.json")


def get_repo_path_from_url(repo_url: str) -> pathlib.Path:
    repo_name = repo_url.split("/")[-1]
    return HOME_DIR / repo_name


def get_short_commit_id(commit_id: str) -> str:
    return commit_id[-SHORT_COMMIT_ID_LENGTH:]


def get_github_token():
    return os.getenv("GITHUB_TOKEN")


AGENT_PR_CONTENT_INPUT_FILE = HOME_DIR / "pr_history.md"
AGENT_ISSUE_CONTENT_INPUT_FILE = HOME_DIR / "issue.md"
AGENT_INSTRUCTIONS_FILE = HOME_DIR / "instructions.txt"


def write_run_metadata(run_uuid: uuid.UUID, commit_id: str) -> None:
    with open(RUN_METADATA_FILE, "w") as f:
        json.dump({"run_uuid": run_uuid, "commit_id": commit_id}, f)


def run_install_script(repo_install_script: str):
    result = os.system(f"set -euo pipefail; bash {repo_install_script}")
    if result != 0:
        raise Exception(f"Failed to run install script {repo_install_script}")


def get_issue_data(
    github_client: github.Github, repo_url: str, issue_number: int
) -> str:
    owner, repo = repo_url.split("/")[-2:]
    base_url = f"https://api.github.com/repos/{owner}/{repo}"
    issue_response = requests.get(f"{base_url}/issues/{issue_number}")
    issue_response.raise_for_status()
    return issue_response.json()


def get_issue_content(
    github_client: github.Github, repo_url: str, issue_number: int
) -> str:
    # TODO: Make a better version of this, just text dump for now
    issue_data = get_issue_data(github_client, repo_url, issue_number)
    return json.dumps(issue_data)


def get_pr_data(repo_url: str, pr_number: int) -> dict:
    owner, repo = repo_url.split("/")[-2:]
    base_url = f"https://api.github.com/repos/{owner}/{repo}"
    pr_response = requests.get(f"{base_url}/pulls/{pr_number}")
    pr_response.raise_for_status()
    comments_response = requests.get(f"{base_url}/issues/{pr_number}/comments")
    comments_response.raise_for_status()
    review_comments_response = requests.get(f"{base_url}/pulls/{pr_number}/comments")
    review_comments_response.raise_for_status()

    pr_data = {
        "pr": pr_response.json(),
        "comments": comments_response.json(),
        "review_comments": review_comments_response.json(),
    }

    return pr_data


def get_pr_content(github_client: github.Github, repo_url: str, pr_number: int) -> str:
    # TODO: Make a better version of this, just text dump for now
    pr_data = get_pr_data(repo_url, pr_number)
    return json.dumps(pr_data)


def write_file_for_agent(file_path: pathlib.Path, content: str) -> None:
    with open(file_path, "w") as f:
        f.write(content)


def setup_agent_state(agent_state: dict | None) -> dict | None:
    # TODO
    return agent_state


def make_request_to_github(
    method: str, repo_url: str, endpoint: str, payload: dict | None = None
) -> requests.Response:
    owner, repo_name = repo_url.split("/")[-2:]
    url = f"https://api.github.com/repos/{owner}/{repo_name}/{endpoint}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {get_github_token()}",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
    response = requests.request(method, url, headers=headers, json=payload)
    raw_curl = f"curl -X {method} -H 'Accept: application/vnd.github+json' -H 'Authorization: Bearer {get_github_token()}' -H 'X-GitHub-Api-Version: 2022-11-28' -H 'Content-Type: application/json' {url} {f"-d '{json.dumps(payload)}'" if payload else ''}"
    print("\n" + raw_curl + "\n")
    response.raise_for_status()
    return response


def setup(
    repo_url: str,
    issue_number: int,
    instructions: str,
    repo_install_script: str | None = None,
    pr_number: int | None = None,
    agent_state: dict | None = None,
    branch: str | None = None,
    commit_id: str | None = None,
    home_dir: str | None = None,
) -> tuple[github.Repository.Repository, uuid.UUID, dict | None]:
    if not get_github_token():
        raise Exception("GITHUB_TOKEN environment variable not set")

    github_client = github.Github(get_github_token())
    owner, repo_name = repo_url.split("/")[-2:]
    repo = github_client.get_repo(f"{owner}/{repo_name}")

    if repo_install_script:
        run_install_script(repo_install_script)

    if commit_id:
        repo.get_commit(commit_id)
    else:  # Get the latest commit
        commit_id = repo.get_commits()[0].sha
    assert commit_id is not None
    short_commit_id = get_short_commit_id(commit_id)
    print(commit_id)

    if branch:
        # See if the branch exists
        try:
            make_request_to_github("GET", repo_url, f"branches/{branch}")
        except requests.exceptions.HTTPError:
            raise Exception(f"Branch {branch} does not exist")

    try:
        # See if a source branch exists for this commit
        make_request_to_github(
            "GET",
            repo_url,
            f"branches/{branch}/fix/{issue_number}/source_{short_commit_id}",
        )
    except requests.exceptions.HTTPError:
        # If not, create a source branch for this commit
        print(f"Creating source branch for commit {commit_id}")
        try:
            make_request_to_github(
                "POST",
                repo_url,
                "git/refs",
                {
                    "ref": f"refs/heads/{branch+'/' if branch else ''}fix/{issue_number}/source_{short_commit_id}",
                    "sha": commit_id,
                },
            )
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 422:
                print(
                    f"Source branch {branch+'/' if branch else ''}fix/{issue_number}/source_{short_commit_id} already exists"
                )
            else:
                raise e

    issue_content = get_issue_content(github_client, repo_url, issue_number)
    write_file_for_agent(AGENT_ISSUE_CONTENT_INPUT_FILE, issue_content)

    if pr_number:
        pr_content = get_pr_content(github_client, repo_url, pr_number)
        write_file_for_agent(AGENT_PR_CONTENT_INPUT_FILE, pr_content)
    else:
        write_file_for_agent(AGENT_PR_CONTENT_INPUT_FILE, "")

    write_file_for_agent(AGENT_INSTRUCTIONS_FILE, instructions)

    agent_state = setup_agent_state(agent_state)

    write_run_metadata(run_uuid, commit_id)

    return repo, run_uuid, agent_state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo_url",
        type=str,
        required=False,
        default="https://github.com/MeganKW/vivaria",
    )
    parser.add_argument("--issue_number", type=int, required=False, default=63)
    parser.add_argument(
        "--instructions", type=str, required=False, default="Fix the issue"
    )
    parser.add_argument("--repo_install_script", type=str, required=False)
    parser.add_argument("--pr_number", type=int, required=False)
    parser.add_argument("--home_dir", type=str, required=False, default="~")

    args = parser.parse_args()

    setup(
        repo_url=args.repo_url,
        issue_number=args.issue_number,
        instructions=args.instructions,
        repo_install_script=args.repo_install_script,
        pr_number=args.pr_number,
        home_dir=args.home_dir,
    )


if __name__ == "__main__":
    main()
