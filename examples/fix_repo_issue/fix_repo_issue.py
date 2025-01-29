# TODO: Should I also have sub issues grab their parent issue content?
# TODO: Figure out how to hook up agents and agent state

import argparse
import os
import pathlib
import uuid

from inspect_ai import Task, eval, task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import Score, Target, accuracy, scorer, stderr
from inspect_ai.solver import TaskState, basic_agent
from inspect_ai.util import sandbox

from src import (
    format_issue_content,
    format_pr_content,
    get_issue_or_pr_data,
    github_interaction,
    task_schema,
)

DEFAULT_SOLVER = [basic_agent(message_limit=1)]

LOCAL_BRANCH_NAME = "local_fix"
AGENT_PR_BODY_FILE = pathlib.Path("pr_body.md")


def get_remote_url(repo_url: str, github_token: str) -> str:
    owner, repo_name = repo_url.split("/")[-2:]
    return f"https://{github_token}@github.com/{owner}/{repo_name}"


@scorer(metrics=[accuracy(), stderr()])
def pr_and_end(repo_url: str, issue_number: int, commit_id: str, remote: str, github_token: str):
    async def score(state: TaskState, target: Target):
        run_uuid = str(uuid.uuid4())
        labels = []
        base_branch_name = github_interaction.get_remote_base_branch_name(issue_number, commit_id)
        head_branch_name = github_interaction.get_run_head_branch_name(run_uuid)

        # Make a local copy of the fix branch with the run_uuid as the name
        owner, repo_name = repo_url.split("/")[-2:]
        try:
            result = await sandbox().exec(
                cmd=["git", "checkout", "local_fix"],
                cwd=f"/app/{repo_name}",
            )
            assert result.returncode == 0
        except Exception:
            print(f"FAILED TO CHECKOUT LOCAL FIX BRANCH, failed with error: {result.stderr}")
            print(f"stdout: {result.stdout}")
            return Score(value=0, explanation="Failed to checkout local fix branch")

        if not github_interaction.remote_base_branch_exists(
            repo_url, issue_number, commit_id, github_token
        ):
            github_interaction.create_remote_base_branch(
                repo_url, issue_number, commit_id, github_token
            )
        set_remote_url_command = [
            "git",
            "remote",
            "set-url",
            remote,
            get_remote_url(repo_url, github_token),
        ]
        # Set the remote URL
        result = await sandbox().exec(
            cmd=set_remote_url_command,
            cwd=f"/app/{repo_name}",
            env={"GITHUB_TOKEN": github_token},
        )
        if result.returncode != 0:
            raise Exception(
                f"Failed to set remote URL with error: \
                    {result.stderr}\n Command: {' '.join(set_remote_url_command)}"
            )

        # Push the branch to the remote
        push_command = [
            "git",
            "push",
            remote,
            f"{LOCAL_BRANCH_NAME}:{head_branch_name}",
        ]
        result = await sandbox().exec(
            cmd=push_command,
            cwd=f"/app/{repo_name}",
            env={"GITHUB_TOKEN": github_token},
        )
        if result.returncode != 0:
            raise Exception(
                f"Failed to push branch to remote {remote} at \
                {repo_url} with error: {result.stderr}\n Command: {' '.join(push_command)}"
            )

        # Read the PR body from the file
        try:
            pr_body = await sandbox().read_file(f"/app/{repo_name}/{AGENT_PR_BODY_FILE.name}")
        except FileNotFoundError:
            pr_body = "[NO PR BODY FILE FOUND]"
            labels.append("no_pr_body_file")

        github_interaction.create_labels_if_not_exists(repo_url, github_token)
        # Make request to PR
        github_interaction.make_request_to_github(
            "POST",
            repo_url,
            "pulls",
            github_token,
            {
                "title": f"Issue #{issue_number} Agent <agent> Run {run_uuid}",
                "body": pr_body,
                "head": head_branch_name,
                "base": base_branch_name,
                "labels": ["agent"],
            },
        )

        return Score(value=1)

    return score


def get_latest_commit_id(repo_url: str, github_token: str) -> str:
    response = github_interaction.make_request_to_github("GET", repo_url, "commits", github_token)
    commits = response.json()
    return commits[0]["sha"]


def get_instructions(repo_url: str, commit_id: str) -> str:
    instructions = f"""Your task is to fix an issue on a repo.
    In this directory you will be provided with issue, plus potentially previous pr and 
    code review contents as txt files.
    
    To work on this task you should:

    1. If the repo is not already present, clone it from {repo_url} using git clone {repo_url}
    2. cd into the provided repo directory
    3. use git checkout to checkout this commit: {commit_id}
    4. make a new branch called '{LOCAL_BRANCH_NAME}' 
        using git checkout -b {LOCAL_BRANCH_NAME} {commit_id}
    5. You should then make changes to the code in this branch, and commit those changes.
    6. You also must create a {AGENT_PR_BODY_FILE.name} file in the
        same directory as the instructions.txt file, which will contain
        the body of the pull request you will make.

    You do not need to make the PR yourself, code will run after you have finished to do this.
    """
    return instructions


def create_sample(
    repo_url: str,
    commit_id: str,
    github_token: str,
    pr_data_list: list[task_schema.GitHubPRResponse],
    issue_data_list: list[task_schema.GitHubIssueResponse],
    repo_install_script: str | pathlib.Path | None,
) -> Sample:
    owner, repo_name = repo_url.split("/")[-2:]
    sample_id = f"{owner}-{repo_name}-{commit_id}"

    issue_content_dict = {}
    pr_content_dict = {}

    for issue_data in issue_data_list:
        issue_number = issue_data.data.repository.issue.number
        issue_content = format_issue_content.format_issue_data(issue_data)  # type: ignore
        issue_content_dict[f"issue_{issue_number}.txt"] = issue_content
    for pr_data in pr_data_list:
        pr_number = pr_data.data.repository.pullRequest.number
        pr_content = format_pr_content.format_pr_data(pr_data)  # type: ignore
        pr_content_dict[f"pr_{pr_number}.txt"] = pr_content

    return Sample(
        id=sample_id,
        input="Look at the instructions.txt file for task instructions.",
        files={
            "instructions.txt": get_instructions(repo_url, commit_id),
            **issue_content_dict,
            **pr_content_dict,
            **({"repo_install_script.sh": str(repo_install_script)} if repo_install_script else {}),
        },
        sandbox=("docker", "compose.yaml"),
        metadata={
            "commit_id": commit_id,
            "owner": owner,
            "repo_name": repo_name,
            "repo_url": repo_url,
            "sample_id": sample_id,
        },
        setup=get_setup_command(
            repo_url,
            repo_name,
            commit_id,
            github_token,
            LOCAL_BRANCH_NAME,
            repo_install_script,
        ),
    )


def get_setup_command(
    repo_url: str,
    repo_name: str,
    commit_id: str,
    github_token: str,
    local_branch_name: str,
    repo_install_script: str | pathlib.Path | None,
) -> str:
    # The below command is used to set up the environment
    # The http config options are to avoid RPC errors
    # To reduce install times we also only fetch
    # NOTE: REMEMBER TO ADD BACK git clone {repo_url}
    command = f"""
set -eufx -o pipefail

apt-get update
apt-get install -y git

export GITHUB_TOKEN="{github_token}"


git config --global http.version HTTP/1.1
git config --global http.postBuffer 524288000


cd {repo_name}
git config --global user.email "agent@example.com"
git config --global user.name "Agent"
git checkout {commit_id}
git checkout -b {local_branch_name} {commit_id}
touch {AGENT_PR_BODY_FILE.name}
git add {AGENT_PR_BODY_FILE.name}
git commit -m "Add {AGENT_PR_BODY_FILE.name} file"

"""
    if repo_install_script:
        command += f"bash {repo_install_script}"
    return command


@task
def fix_repo_issue(
    repo_url: str,
    issue_number: int,
    github_token: str | None = os.getenv("GITHUB_TOKEN"),
    issue_data_list: list[dict] | None = None,
    pr_data_list: list[dict] | None = None,
    commit_id: str | None = None,
    repo_install_script: str | pathlib.Path | None = None,
    live_pull_issues: list[int] | None = None,
    live_pull_prs: list[int] | None = None,
    remote: str = "origin",
    agent=DEFAULT_SOLVER,
) -> Task:
    """
    Task for getting the agent to fix an issue on a repo. The agents solution is made into a PR.

    Parameters
    ----------
    repo_url : str
        The url of the repo to pull issues from and to push the PR to.
    issue_number : int
        The number of the issue being targeted.
    github_token : str
        The github token to use for the task.
        This should have write access to the repo being pushed to - and read access
        to the repo being pulled from (if live_pull_issue or live_pull_prs is True).
        NOTE: The agent will *not* have access to this token.
    issue_data_list : list[dict] | None, optional
        The content of the issue.md file.
        Shows the contents of the issue page in a specific format.
        Populate this with data made from `pull_git_content.get_issue_content`.
    pr_data_list : list[dict] | None, optional
        The content of PR(s) and any associated code reviews.
        Use `pull_git_content.get_pr_content` to generate.
        Can include multiple PRs.
    commit_id : str | None, optional
        The commit id from which to start the task.
        If not provided, the latest commit id from the main branch will be used.
    repo_install_script : str | pathlib.Path | None, optional
        An optional additional script to be run in the agent's
        environment to perform any additional setup.
    live_pull_issue : bool, optional
        If True, the issue content will be pulled from the repo live.
        Not recommended for experiments involving many runs.
        Multiple live runs are likely to hit github APIrate limits.
    live_pull_prs : list[int] | None, optional
        The numbers of the PRs to pull from the repo.
    remote : str, optional
        The remote to push the PR to. Usually this will be "origin".
    agent : Solver, optional
        The agent to use for the task.
    """
    if not live_pull_issues and not issue_data_list:
        raise ValueError("Must provide either live_pull_issues or issue_data")
    if live_pull_issues and issue_data_list:
        raise ValueError("Cannot provide both live_pull_issues and issue_data")
    if live_pull_prs and pr_data_list:
        raise ValueError("Cannot provide both live_pull_prs and pr_data_list")
    if not github_token:
        raise ValueError("Must provide github_token")

    owner, repo_name = repo_url.split("/")[-2:]

    if commit_id is None:
        commit_id = get_latest_commit_id(repo_url, github_token)

    issue_data_list = []
    if live_pull_issues is not None:
        for issue_number in live_pull_issues:
            issue_data = get_issue_or_pr_data.get_issue_data(
                owner, repo_name, issue_number, max_num=100
            )
            issue_data_list.append(issue_data)

    if live_pull_prs is not None:
        pr_data_list = []
        for pr_number in live_pull_prs:
            pr_data = get_issue_or_pr_data.get_pr_data(owner, repo_name, pr_number, max_num=100)
            pr_data_list.append(pr_data)

    assert issue_number is not None
    assert issue_data_list is not None
    assert github_token is not None

    if pr_data_list is not None:
        typed_pr_data_list = [
            task_schema.GitHubPRResponse.model_validate(pr_data)
            for pr_data in pr_data_list
            if pr_data is not None
        ]
    else:
        typed_pr_data_list = []

    typed_issue_data_list = [
        task_schema.GitHubIssueResponse.model_validate(issue_data)
        for issue_data in issue_data_list
        if issue_data is not None
    ]
    sample = create_sample(
        repo_url,
        commit_id,
        github_token,
        typed_pr_data_list,
        typed_issue_data_list,
        repo_install_script,
    )
    owner, repo_name = repo_url.split("/")[-2:]
    return Task(
        dataset=[sample],
        solver=agent,
        scorer=pr_and_end(repo_url, issue_number, commit_id, remote, github_token),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-url", type=str, required=True, help="The URL of the repository to work on"
    )
    parser.add_argument(
        "--issue-number", type=int, required=True, help="The number of the issue to fix"
    )
    parser.add_argument("--github-token", type=str, help="GitHub token for authentication")
    parser.add_argument("--commit-id", type=str, help="The commit ID to start from")
    parser.add_argument("--repo-install-script", type=str, help="Path to repo install script")
    parser.add_argument(
        "--live-pull-issues", type=int, nargs="*", help="List of issue numbers to pull live"
    )
    parser.add_argument(
        "--live-pull-prs", type=int, nargs="*", help="List of PR numbers to pull live"
    )
    parser.add_argument("--remote", type=str, default="origin", help="Remote name")

    args = parser.parse_args()

    return eval(
        fix_repo_issue(
            repo_url=args.repo_url,
            issue_number=args.issue_number,
            github_token=args.github_token,
            commit_id=args.commit_id,
            repo_install_script=args.repo_install_script,
            live_pull_issues=args.live_pull_issues,
            live_pull_prs=args.live_pull_prs,
            remote=args.remote,
        ),
        model="openai/gpt-4o",
    )


if __name__ == "__main__":
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        raise ValueError("GITHUB_TOKEN environment variable is not set")
    main()
