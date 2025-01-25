import json
import os
import pathlib
import uuid

import git
import github
import github.Repository
import requests

from inspect_ai import Task, eval, solver, task
from inspect_ai.dataset import example_dataset
from inspect_ai.scorer._scorer import scorer
from inspect_ai.solver import (
    Generate,
    Solver,
    TaskState,
    solver,
    system_message,
    use_tools,
    chain_of_thought,
    generate,
)

DEFAULT_SOLVER = [chain_of_thought(), generate()]
SHORT_COMMIT_ID_LENGTH = 6
AGENT_PR_CONTENT_INPUT_FILE = pathlib.Path("pr_history.md")
AGENT_ISSUE_CONTENT_INPUT_FILE = pathlib.Path("issue.md")
AGENT_INSTRUCTIONS_FILE = pathlib.Path("instructions.txt")
AGENT_PR_CONTENT_OUTPUT_FILE = pathlib.Path("pr_content.md")
RUN_METADATA_FILE = pathlib.Path(".run_metadata.json")
HOME_DIR = pathlib.Path("~")


def write_run_metadata(run_uuid: uuid.UUID, commit_id: str) -> None:
    with open(RUN_METADATA_FILE, "w") as f:
        json.dump({"run_uuid": run_uuid, "commit_id": commit_id}, f)


def read_run_metadata() -> dict:
    with open(RUN_METADATA_FILE, "r") as f:
        return json.load(f)


def get_github_token():
    return os.getenv("GITHUB_TOKEN")


def clone_repo(
    github_client: github.Github, repo_url: str
) -> github.Repository.Repository:
    repo = github_client.get_repo(repo_url)
    return repo


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


def get_repo_path_from_url(repo_url: str) -> pathlib.Path:
    repo_name = repo_url.split("/")[-1]
    return HOME_DIR / repo_name


def write_file_for_agent(file_path: pathlib.Path, content: str) -> None:
    with open(file_path, "w") as f:
        f.write(content)


def get_short_commit_id(commit_id: str) -> str:
    return commit_id[-SHORT_COMMIT_ID_LENGTH:]


def read_pr_content_from_agent(agent_pr_content_file: pathlib.Path) -> dict:
    with open(agent_pr_content_file, "r") as f:
        return json.load(f)


def make_pr_body_content(agent_pr_content: dict) -> str:
    # TODO
    return ""


def setup_agent_state(agent_state: dict | None) -> dict | None:
    # TODO
    return agent_state



def setup(
    repo_url: str,
    issue_number: int,
    instructions: str,
    repo_install_script: str | None = None,
    pr_number: int | None = None,
    agent_state: dict | None = None,
    branch: str | None = None,
    commit_id: str | None = None,
) -> tuple[github.Repository.Repository, uuid.UUID, dict | None]:
    github_client = github.Github(get_github_token())
    repo = clone_repo(github_client, repo_url)

    if repo_install_script:
        run_install_script(repo_install_script)

    if commit_id:
        repo.get_commit(commit_id)
        current_commit_id = commit_id
    else:  # Get the latest commit
        commit_id = repo.get_commit(commit_id).sha
    short_commit_id = get_short_commit_id(commit_id)

    if branch:
        repo.get_branch(branch)

    try:
        repo.get_branch(f"fix/{issue_number}/source_{short_commit_id}")
    except github.GithubException:
        repo.create_git_ref(
            f"refs/heads/fix/{issue_number}/source_{short_commit_id}", commit_id
        )

    run_uuid = uuid.uuid4()
    repo.create_git_ref(
        f"refs/heads/fix/{issue_number}/source_{short_commit_id}/{run_uuid}", commit_id
    )

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

    agent_pr_content = read_pr_content_from_agent(AGENT_PR_CONTENT_INPUT_FILE)

    # Augment the PR content with human friendly content (like how to access the transcript of the run)
    pr_content = make_pr_body_content(agent_pr_content)

    # Make a PR from the branch fix/<issue_number>/source_<short_commit_id>/<uuid v4> to the branch fix/<issue_number>/source_<short_commit_id>
    repo.create_pull(
        title=f"Fix {issue_number} - run {run_uuid}",
        body=pr_content,
        head=branch_name,
        base=f"fix/{issue_number}/source_{short_commit_id}",
    )


@task
def fix_repo_issue(
    repo_url: str,
    issue_number: int,
    instructions: str,
    repo_install_script: str | None = None,
    branch: str = "main",
    commit_id: str | None = None,
    pr_number: int | None = None,
    remote_name: str = "origin",
    agent_state: dict | None = None,
    agent=DEFAULT_SOLVER,
) -> Task:
    return Task(
        dataset=example_dataset("theory_of_mind"),
        solver=agent,
        scorer=finalize(
            repo_url=repo_url,
            issue_number=issue_number,
            remote_name=remote_name,
        ),
        sandbox = "docker",
        setup=setup(
            repo_url=repo_url,
            issue_number=issue_number,
            instructions=instructions,
            repo_install_script=repo_install_script,
            branch=branch,
            commit_id=commit_id,
            pr_number=pr_number,
            agent_state=agent_state,
        ),
    )


if __name__ == "__main__":
    eval(
        fix_repo_issue(
            repo_url="https://github.com/inspect-ai/inspect-ai",
            issue_number=1,
            instructions="Fix the issue",
            repo_install_script="",
            branch="main",
            commit_id=None,
            pr_number=None,
            remote_name="origin",
            agent_state=None,
        ),
        model="openai/gpt-4o",
    )
