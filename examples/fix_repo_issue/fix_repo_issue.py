import pathlib

from inspect_ai import Task, eval, task
from inspect_ai.dataset import example_dataset
from inspect_ai.solver import chain_of_thought, generate

DEFAULT_SOLVER = [chain_of_thought(), generate()]
SHORT_COMMIT_ID_LENGTH = 6
AGENT_PR_CONTENT_INPUT_FILE = pathlib.Path("pr_history.md")
AGENT_ISSUE_CONTENT_INPUT_FILE = pathlib.Path("issue.md")
AGENT_INSTRUCTIONS_FILE = pathlib.Path("instructions.txt")


@task
def fix_repo_issue(

    agent=DEFAULT_SOLVER,
) -> Task:
    return Task(
        dataset=example_dataset("theory_of_mind"),
        solver=agent,
        sandbox=("docker", "compose.yaml"),
    )


if __name__ == "__main__":
    eval(
        fix_repo_issue(
            # repo_url="https://github.com/UKGovernmentBEIS/inspect_ai",
            # issue_number=1174,
            # instructions="Fix the issue",
            # repo_install_script="",
            # branch="main",
            # commit_id=None,
            # pr_number=None,
            # remote_name="origin",
            # agent_state=None,
            agent=DEFAULT_SOLVER,
        ),
        model="openai/gpt-4o",
    )
