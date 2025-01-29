import argparse
import json
import os

import requests


def make_issue_graph_ql_query(
    owner: str,
    repo: str,
    issue_number: int,
    max_num: int = 100,
) -> str:
    return f"""query {{
        repository(name: "{repo}", owner: "{owner}") {{
            issue(number: {issue_number}) {{
                number
                title
                body
                createdAt
                author {{ login }}
                labels(first: {max_num}) {{
                    nodes {{
                        name
                        description
                        color
                    }}
                    pageInfo {{
                        hasNextPage
                        endCursor
                    }}
                }}
                comments(first: {max_num}) {{
                    nodes {{
                        author {{ login }}
                        body
                        createdAt
                    }}
                    pageInfo {{
                        hasNextPage
                        endCursor
                    }}
                }}
            }}
        }}
    }}"""


def get_data_file_name(issue_or_pr: str, owner: str, repo: str, number: int) -> str:
    return (
        f"issue_{owner}_{repo}_{number}.json"
        if issue_or_pr == "issue"
        else f"pr_{owner}_{repo}_{number}.json"
    )


def make_pr_data_graph_ql_query(owner: str, repo: str, pr_number: int, max_num: int = 100) -> str:
    return f"""query {{
        repository(name: "{repo}", owner: "{owner}") {{
            pullRequest(number: {pr_number}) {{
                number
                title
                body
                createdAt
                author {{ login }}
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
                            pageInfo {{
                                hasNextPage
                                endCursor
                            }}
                        }}
                    }}
                    pageInfo {{
                        hasNextPage
                        endCursor
                    }}
                }}
                comments(first: {max_num}) {{
                    nodes {{
                        author {{ login }}
                        createdAt
                        body
                    }}
                    pageInfo {{
                        hasNextPage
                        endCursor
                    }}
                }}
            }}
        }}
    }}"""


def make_graph_ql_request(query: str) -> dict:
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


# Could have implemented pagination handling, but felt like overkill.
def all_data_fetched(data: dict) -> bool:
    """Recursively look through for nodes fields checking that all pages have been fetched"""
    for key, value in data.items():
        if isinstance(value, dict) and "nodes" in value:
            if value["pageInfo"]["hasNextPage"]:
                return False
        elif isinstance(value, list):
            for item in value:
                if not all_data_fetched(item):
                    return False
    return True


def get_pr_data(owner: str, repo: str, pr_number: int, max_num: int) -> dict:
    query = make_pr_data_graph_ql_query(owner, repo, pr_number, max_num)
    result = make_graph_ql_request(query)
    if not all_data_fetched(result):
        raise ValueError("Not all data fetched, increase max_num of graphql query")
    return result


def get_issue_data(owner: str, repo: str, issue_number: int, max_num: int) -> dict:
    query = make_issue_graph_ql_query(owner, repo, issue_number, max_num)
    result = make_graph_ql_request(query)
    if not all_data_fetched(result):
        raise ValueError("Not all data fetched, increase max_num of graphql query")
    return result


def _write_content(content: str, output_dir: str, filename: str) -> None:
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, filename)
    with open(output_path, "w") as f:
        f.write(content)


def parse_url(url: str) -> tuple[str, str, str, int]:
    """Parse a GitHub URL into owner, repo,
    whether it's an issue or a PR, and the number of the issue or PR

    Returns: (issue_or_pr, owner, repo, number)
    """
    _, _, _, owner, repo, issue_or_pr, number = url.split("/")
    if issue_or_pr == "issues":
        return "issue", owner, repo, int(number)
    elif issue_or_pr == "pull":
        return "pr", owner, repo, int(number)
    else:
        raise ValueError(
            f"Invalid URL: {url}, should have format \
                https://github.com/owner/repo/<issues or pull>/number"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pull GitHub issue or PR content. \
            Either provide a URL or all of the following arguments: \
            --owner, --repo, --output-dir and one of either --issue or --prs"
    )
    parser.add_argument("url", help="URL to issue or PR")
    parser.add_argument("--owner", help="GitHub owner")
    parser.add_argument("--repo", help="GitHub repository")
    parser.add_argument("--output-dir", required=True, help="Directory to save output files")
    parser.add_argument("--issue", type=int, help="Issue number to fetch")
    parser.add_argument("--prs", type=int, nargs="+", help="One or more PR numbers to fetch")
    parser.add_argument(
        "--max-num",
        type=int,
        default=100,
        help="Maximum number of nodes to fetch in graphQL query. \
            Script will warn by error-ing out if not all data has been fetched",
    )
    args = parser.parse_args()

    error_flag = False
    if not args.output_dir:
        parser.error("Must provide --output-dir")

    # Check that if URL is provided, none of the other arguments are
    if args.url and (args.owner or args.repo or args.issue or args.prs):
        error_flag = True

    # Check that if URL is not provided, all of the other arguments are
    if not args.url:
        if not (args.owner and args.repo and (args.issue or args.prs)):
            error_flag = True

    if error_flag:
        parser.error(
            "Either provide 1. URL and --output-dir or 2. ALL of the following arguments: \
                --owner, --repo, --output-dir and ONE of either --issue or --prs"
        )

    if args.url:
        content_type, owner, repo, number = parse_url(args.url)
        if content_type == "issue":
            args.issue = number
        else:
            args.prs = [number]
    else:
        owner = args.owner
        repo = args.repo

    if args.issue:
        issue_data = get_issue_data(owner, repo, args.issue, args.max_num)
        _write_content(
            json.dumps(issue_data, indent=2),
            args.output_dir,
            get_data_file_name("issue", owner, repo, args.issue),
        )

    if args.prs:
        for pr_number in args.prs:
            pr_data = get_pr_data(owner, repo, pr_number, args.max_num)
            _write_content(
                json.dumps(pr_data, indent=2),
                args.output_dir,
                get_data_file_name("pr", owner, repo, pr_number),
            )


if __name__ == "__main__":
    main()
