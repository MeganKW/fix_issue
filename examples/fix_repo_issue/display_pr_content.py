import textwrap


def is_review(data: dict) -> bool:
    if "bodyText" in data:
        return True
    return False


def format_review(review: dict) -> str:
    review_comments = review["comments"]["nodes"]
    formatted_review_comments = []
    # Sort by created at
    review_comments.sort(key=lambda x: x["createdAt"])
    for review_comment in review_comments:
        formatted_review_comments.append(format_review_comment(review_comment))

    msg = f"""[{review['createdAt']}] REVIEW
{review['author']['login']}:
{review['bodyText']}
    """
    for comment in formatted_review_comments:
        msg += textwrap.indent(comment, "       ") + "\n\n"
    return msg


def format_review_comment(review_comment_data: dict) -> str:
    if review_comment_data["subjectType"] == "LINE":
        code_context = (
            "==========================================\n"
            + "\n".join(review_comment_data["diffHunk"].split("\n")[-4:])
            + "\n=========================================="
        )
    else:
        code_context = (
            "==========================================\n"
            + review_comment_data["diffHunk"]
            + "\n=========================================="
        )

    msg = f"""[{review_comment_data['createdAt']}]{'[OUTDATED]' if review_comment_data["position"] is None else ''}
Code context:
{code_context}
{review_comment_data["author"]["login"]}:
{review_comment_data["body"]}
    """
    return msg


def format_comment(comment: dict) -> str:
    # Print keys of comment
    msg = f"""[{comment['createdAt']}]
{comment['author']['login']}:
{comment['body']}
    """
    return msg


def format_pr_data(pr_response: dict) -> str:
    pr_data = pr_response["data"]["repository"]["pullRequest"]
    title = pr_data["title"]
    body = pr_data["body"]

    comments: list[dict] = pr_data["comments"]["nodes"]
    reviews: list[dict] = pr_data["reviews"]["nodes"]
    reviews.sort(key=lambda x: x["createdAt"])
    reviews_and_comments = reviews + comments
    reviews_and_comments.sort(key=lambda x: x["createdAt"])
    formatted_reviews_and_comments = []
    for obj in reviews_and_comments:
        if is_review(obj):
            formatted_reviews_and_comments.append(format_review(obj))
        else:
            formatted_reviews_and_comments.append(format_comment(obj))

    msg = f"Title: {title}\n"
    msg += f"Body: {body}\n"
    msg += "Comments:\n"
    for comment in formatted_reviews_and_comments:
        msg += comment + "\n\n"
    return msg