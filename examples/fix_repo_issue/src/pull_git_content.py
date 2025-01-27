import argparse
import json
import os

import requests


def get_owner_and_repo_from_url(url: str) -> tuple[str, str]:
    owner, repo = url.split("/")[-2], url.split("/")[-1].replace(".git", "")
    return owner, repo


def get_issue_info(url: str, issue: int) -> dict:
    owner, repo = get_owner_and_repo_from_url(url)
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue}"

    response = requests.get(url)

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to fetch issue data: {response.status_code}")


def get_issue_comments(url: str, issue: int) -> list[dict]:
    owner, repo = get_owner_and_repo_from_url(url)
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue}/comments"

    response = requests.get(url)

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to fetch issue comments: {response.status_code}")


def get_issue_labels(url: str, issue: int) -> list[dict]:
    owner, repo = get_owner_and_repo_from_url(url)
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue}/labels"

    response = requests.get(url)

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to fetch issue labels from {url}: {response.json()}")


def clean_up_comments(comments: list[dict]) -> str:
    if len(comments) == 0:
        return "No comments"

    cleaned = []
    for comment in comments:
        author = comment["user"]["login"]
        body = comment["body"].replace("\r\n", "\n").strip()  # Normalize line endings
        date = comment["created_at"].split("T")[0]  # Get just the date part
        cleaned.append(f"[{date}] {author}: {body}")

    return "\n\n".join(cleaned)


def make_issue_summary(labels: list[dict], comments: list[dict], issue: dict) -> str:
    clean_comments = clean_up_comments(comments)

    return f"Issue {issue['number']}: {issue['title']}\n\n{issue['body']}\n\nLabels: {labels}\n\nComments: {clean_comments}"


def get_issue_content(
    url: str,
    issue: int,
) -> tuple[str, dict]:
    issue_labels = get_issue_labels(url, issue)
    issue_comments = get_issue_comments(url, issue)
    issue_info = get_issue_info(url, issue)
    raw_data = {
        "issue_labels_response": issue_labels,
        "issue_comments_response": issue_comments,
        "issue_info_response": issue_info,
    }
    return make_issue_summary(issue_labels, issue_comments, issue_info), raw_data


def make_request_to_graph_ql(repo_url: str, pr_number: int) -> dict:
    max_num = 100
    owner, repo = get_owner_and_repo_from_url(repo_url)
    query = f"""query {{
        repository(name: "{repo}", owner: "{owner}") {{
            pullRequest(number: {pr_number}) {{
                title
                body
                reviews(first: {max_num}) {{
                    nodes {{
                        bodyText
                        createdAt
                        author {{ login }}
                        comments(first: {max_num}) {{
                            nodes {{
                                author {{ login }}
                                body
                                createdAt
                                diffHunk
                                position
                                subjectType
                            }}
                        }}
                    }}
                }}
                comments(first: {max_num}) {{
                    nodes {{
                        author {{ login }}
                        createdAt
                        body
                    }}
                    totalCount
                }}
            }}
        }}
    }}"""
    headers = {
        "Authorization": f"bearer {os.environ.get('GITHUB_TOKEN')}",
        "Content-Type": "application/json",
    }
    response = requests.post(
        "https://api.github.com/graphql", headers=headers, json={"query": query}
    )

    if not response.ok:
        raise requests.exceptions.HTTPError(f"GraphQL request failed: {response.text}")

    return response.json()


def get_pr_data(repo_url: str, pr_number: int) -> tuple[dict, dict]:
    try:
        owner, repo = repo_url.split("/")[-2:]
        base_url = f"https://api.github.com/repos/{owner}/{repo}"
        pr_response = requests.get(f"{base_url}/pulls/{pr_number}")
        pr_response.raise_for_status()
        comments_response = requests.get(f"{base_url}/issues/{pr_number}/comments")
        comments_response.raise_for_status()
        review_comments_response = requests.get(
            f"{base_url}/pulls/{pr_number}/comments"
        )
        review_comments_response.raise_for_status()
        graph_ql_response = make_request_to_graph_ql(repo_url, pr_number)
    except requests.exceptions.HTTPError as e:
        print(f"Error getting PR data for {repo_url} {pr_number}: {e}")
        return {}, {}

    pr_data = {
        "pr": pr_response.json(),
        "comments": comments_response.json(),
        "review_comments": review_comments_response.json(),
        "graph_ql_response": graph_ql_response,
    }

    raw_data = {
        "pr": pr_response.json(),
        "comments": comments_response.json(),
        "review_comments": review_comments_response.json(),
        "graph_ql_response": graph_ql_response,
    }

    return pr_data, raw_data


def get_pr_content(repo_url: str, pr_numbers: list[int]) -> tuple[str, list[dict]]:
    pr_data_list = []
    raw_data_list = []
    for pr_number in pr_numbers:
        pr_data, raw_data = get_pr_data(repo_url, pr_number)
        pr_data_list.append(pr_data)
        raw_data_list.append(raw_data)
    return json.dumps(pr_data_list, indent=2), raw_data_list


def _write_content(content: str, output_dir: str, filename: str) -> None:
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, filename)
    with open(output_path, "w") as f:
        f.write(content)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull GitHub issue or PR content")
    parser.add_argument("repo_url", help="GitHub repository URL")
    parser.add_argument(
        "--output-dir", required=True, help="Directory to save output files"
    )
    parser.add_argument(
        "--raw", action="store_true", help="Save raw API responses separately"
    )
    parser.add_argument("--issue", type=int, help="Issue number to fetch")
    parser.add_argument(
        "--pr", type=int, nargs="+", help="One or more PR numbers to fetch"
    )

    args = parser.parse_args()

    if not args.issue and not args.pr:
        parser.error("At least one of --issue or --pr must be specified")

    if args.issue:
        content, raw_data = get_issue_content(args.repo_url, args.issue)
        _write_content(content, args.output_dir, f"issue_{args.issue}.json")
        if args.raw:
            for endpoint, data in raw_data.items():
                _write_content(
                    json.dumps(data, indent=2),
                    args.output_dir,
                    f"issue_{args.issue}_{endpoint}_raw.json",
                )

    if args.pr:
        content, raw_data_list = get_pr_content(args.repo_url, args.pr)
        pr_nums = "_".join(map(str, args.pr))
        _write_content(content, args.output_dir, f"prs_{pr_nums}.json")
        if args.raw:
            for i, raw_data in enumerate(raw_data_list):
                pr_number = args.pr[i]
                for endpoint, data in raw_data.items():
                    _write_content(
                        json.dumps(data, indent=2),
                        args.output_dir,
                        f"pr_{pr_number}_{endpoint}_raw.json",
                    )


if __name__ == "__main__":
    main()
