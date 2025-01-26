# TODO: Should I also have sub issues grab their parent issue content?
# TODO: Figure out how to hook up agents and agent state

import hashlib
import os
import pathlib
import uuid

from inspect_ai import Task, eval, task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import Score, Target, accuracy, scorer, stderr
from inspect_ai.solver import TaskState, basic_agent
from inspect_ai.util import sandbox

from . import end_run, pull_git_content

DEFAULT_SOLVER = [basic_agent()]
LOCAL_BRANCH_NAME = "local_fix"
AGENT_PR_BODY_FILE = pathlib.Path("pr_body.md")


@scorer(metrics=[accuracy(), stderr()])
def pr_and_end(repo_url: str, issue_number: int, commit_id: str, remote: str):
    async def score(state: TaskState, target: Target):
        run_uuid = str(uuid.uuid4())

        # Make a local copy of the fix branch with the run_uuid as the name
        try:
            result = await sandbox().exec(
                cmd=["git", "checkout", "-b", LOCAL_BRANCH_NAME, f"{run_uuid}"]
            )
            assert result.returncode == 0
        except Exception as e:
            return Score(
                value=0, explanation=f"Failed to checkout local fix branch: {e}"
            )

        if not end_run.remote_base_branch_exists(repo_url, issue_number, commit_id):
            end_run.create_remote_base_branch(repo_url, issue_number, commit_id)

        # Push the branch to the remote
        github_token = os.getenv("GITHUB_TOKEN")
        assert github_token is not None
        result = await sandbox().exec(
            cmd=["git", "push", remote, LOCAL_BRANCH_NAME],
            env={"GITHUB_TOKEN": github_token},
        )
        assert result.returncode == 0

        # Read the PR body from the file
        try:
            with open(AGENT_PR_BODY_FILE, "r") as f:
                pr_body = f.read()
        except FileNotFoundError:
            return Score(value=0, explanation="PR body file not found")

        # Make request to PR
        end_run.make_request_to_github(
            "POST",
            repo_url,
            "pulls",
            {
                "title": f"Agent PR from {run_uuid}",
                "body": pr_body,
                "head": end_run.get_run_head_branch_name(run_uuid),
                "base": end_run.get_remote_base_branch_name(issue_number, commit_id),
            },
        )

        return Score(value=1)

    return score


def get_latest_commit_id(repo_url: str) -> str:
    response = end_run.make_request_to_github("GET", repo_url, "commits")
    commits = response.json()
    return commits[0]["sha"]


def hash_content(content: str | pathlib.Path) -> str:
    if isinstance(content, pathlib.Path):
        content = content.read_text()
    return hashlib.sha256(content.encode()).hexdigest()


def get_instructions(repo_url: str, commit_id: str) -> str:
    instructions = f"""Your task is to fix an issue on a repo.
    In this directory you will be provided with issue contents in issue_contents.txt, plus any associated pr history and code reviews in pr_history.txt (this may be empty).
    To work on this task you should:

    1. If the repo is not already present, clone it from {repo_url} using git clone {repo_url}
    2. cd into the provided repo directory
    3. use git checkout to checkout this commit: {commit_id}
    4. make a new branch called '{LOCAL_BRANCH_NAME}' using git checkout -b {LOCAL_BRANCH_NAME} {commit_id}
    4. You should then make changes to the code in this branch, and commit those changes.
    5. You also must create a {AGENT_PR_BODY_FILE.name} file in the same directory as the instructions.txt file, which will contain the body of the pull request you will make.

    You do not need to make the PR yourself, code will run after you have finished to do this.
    """
    return instructions


def create_sample(
    repo_url: str,
    commit_id: str,
    pr_history: str | pathlib.Path | None,
    repo_install_script: str | pathlib.Path | None,
    issue_content: str | pathlib.Path,
) -> Sample:
    hash_pr_history_content = hash_content(pr_history) if pr_history else ""
    hash_issue_content = hash_content(issue_content)
    owner, repo_name = repo_url.split("/")[-2:]
    sample_id = f"{owner}-{repo_name}-{commit_id}-hash-issue-{hash_issue_content}"
    sample_id += f"-hash-pr-history-{hash_pr_history_content}" if pr_history else ""

    return Sample(
        id=sample_id,
        input="Look at the instructions.txt file for task instructions.",
        files={
            "instructions.txt": get_instructions(repo_url, commit_id),
            "issue_content.txt": str(issue_content),
            "pr_history.txt": str(pr_history) if pr_history else "",
            **(
                {"repo_install_script.sh": str(repo_install_script)}
                if repo_install_script
                else {}
            ),
        },
        sandbox=("docker", "compose.yaml"),
        metadata={
            "commit_id": commit_id,
            "hash_issue_content": hash_issue_content,
            "hash_pr_history_content": hash_pr_history_content,
            "owner": owner,
            "repo_name": repo_name,
            "repo_url": repo_url,
            "sample_id": sample_id,
        },
        setup=str(repo_install_script) if repo_install_script else None,
    )


@task
def fix_repo_issue(
    repo_url: str = "https://github.com/MeganKW/vivaria",
    repo_install_script: str | pathlib.Path | None = None,
    live_pull_issue: int | None = 63,
    live_pull_prs: list[int] | None = None,
    issue_number: int | None = None,
    issue_content: str | pathlib.Path | None = None,
    pr_history: str | pathlib.Path | None = None,
    commit_id: str | None = None,
    remote: str = "origin",
    agent=DEFAULT_SOLVER,
) -> Task:
    if live_pull_issue and issue_content:
        raise ValueError("Cannot provide both live_pull_issue and issue_content")

    if live_pull_prs and pr_history:
        raise ValueError("Cannot provide both live_pull_prs and pr_history")

    if live_pull_issue is not None:
        issue_number = live_pull_issue
    elif issue_number is not None:
        issue_number = issue_number
    else:
        raise ValueError("Must provide either live_pull_issue or issue_number")

    os.environ["REPO_URL"] = repo_url

    if commit_id is None:
        commit_id = get_latest_commit_id(repo_url)

    if live_pull_issue is not None:
        issue_content, _ = pull_git_content.get_issue_content(repo_url, live_pull_issue)

    if live_pull_prs is not None:
        pr_history, _ = pull_git_content.get_pr_content(repo_url, live_pull_prs)

    assert issue_content is not None

    sample = create_sample(
        repo_url, commit_id, pr_history, repo_install_script, issue_content
    )

    return Task(
        dataset=[sample],
        solver=agent,
        scorer=pr_and_end(repo_url, issue_number, commit_id, remote),
    )


if __name__ == "__main__":
    eval(
        fix_repo_issue(
            repo_url="https://github.com/MeganKW/vivaria",
            commit_id="",
            live_pull_issue=63,
            live_pull_prs=None,
            pr_history=None,
            repo_install_script=None,
            issue_content=None,
            agent=DEFAULT_SOLVER,
        ),
        model="openai/gpt-4o",
    )
