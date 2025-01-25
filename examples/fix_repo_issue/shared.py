import os
import pathlib

HOME_DIR = pathlib.Path("~")
SHORT_COMMIT_ID_LENGTH = 6
RUN_METADATA_FILE = pathlib.Path(".run_metadata.json")


def get_repo_path_from_url(repo_url: str) -> pathlib.Path:
    repo_name = repo_url.split("/")[-1]
    return HOME_DIR / repo_name


def get_short_commit_id(commit_id: str) -> str:
    return commit_id[-SHORT_COMMIT_ID_LENGTH:]


def get_github_token():
    return os.getenv("GITHUB_TOKEN")
