import json
import pathlib

TEST_RESPONSE_DIR = pathlib.Path("examples/fix_repo_issue/tests/test_responses")

pr_response = json.load(open(TEST_RESPONSE_DIR / "pr_1161_pr_raw.json"))
pr_comments_response = json.load(open(TEST_RESPONSE_DIR / "pr_1161_comments_raw.json"))
pr_review_comments_response = json.load(
    open(TEST_RESPONSE_DIR / "pr_1161_review_comments_raw.json")
)

pr_data = {
    "pr_response": pr_response,
    "pr_comments_response": pr_comments_response,
    "pr_review_comments_response": pr_review_comments_response,
}


def get_title(pr_data: dict) -> str:
    return pr_data["pr_response"]["title"]


def get_body(pr_data: dict) -> str:
    return pr_data["pr_response"]["body"]


def combine_comments(pr_data: dict) -> list[dict]:
    # Take all the entries from each list by their created at, and then sort them and combine
    review_comments = pr_data["pr_review_comments_response"]
    comments = pr_data["pr_comments_response"]

    # Combine the comments and review comments
    combined = review_comments + comments
    # Sort by created at
    combined.sort(key=lambda x: x["created_at"])
    return combined


def is_review_comment(comment: dict) -> bool:
    if "diff_hunk" in comment:
        return True
    return False


def review_comment_is_outdated(review_comment: dict) -> bool:
    if review_comment["position"] is None:
        return True
    return False


def format_review_comment(review_comment_data: dict) -> str:
    if review_comment_data["subject_type"] == "line":
        code_context = (
            "==========================================\n"
            + "\n".join(review_comment_data["diff_hunk"].split("\n")[-4:])
            + "\n=========================================="
        )
    else:
        code_context = (
            "==========================================\n"
            + review_comment_data["diff_hunk"]
            + "\n=========================================="
        )

    msg = f"""[{review_comment_data['created_at']}]{'[OUTDATED]' if review_comment_data["position"] is None else ''}
Code context:
{code_context}
{review_comment_data["user"]["login"]}:
{review_comment_data["body"]}
    """
    return msg


def format_comment(comment: dict) -> str:
    msg = f"""[{comment['created_at']}]
{comment['user']['login']}:
{comment['body']}
    """
    return msg


def format_pr_data(pr_data: dict) -> str:
    title = get_title(pr_data)
    body = get_body(pr_data)
    comments = combine_comments(pr_data)

    formatted_comments = []
    for comment in comments:
        if is_review_comment(comment):
            formatted_comments.append(format_review_comment(comment))
        else:
            formatted_comments.append(format_comment(comment))

    msg = f"Title: {title}\n"
    msg += f"Body: {body}\n"
    msg += "Comments:\n"
    for comment in formatted_comments:
        msg += comment + "\n\n"
    return msg


def main():
    print(format_pr_data(pr_data))


if __name__ == "__main__":
    main()
