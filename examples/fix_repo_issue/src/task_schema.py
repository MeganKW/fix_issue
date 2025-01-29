from typing import List, Optional

from pydantic import BaseModel


class Author(BaseModel):
    login: str


class Label(BaseModel):
    name: str
    description: str
    color: str


class Comment(BaseModel):
    author: Author
    body: str
    createdAt: str


class ReviewComment(BaseModel):
    author: Author
    body: str
    createdAt: str
    diffHunk: str
    position: int
    subjectType: str


class PageInfo(BaseModel):
    hasNextPage: bool
    endCursor: str | None


class ReviewCommentList(BaseModel):
    nodes: List[ReviewComment]
    pageInfo: PageInfo


class Review(BaseModel):
    bodyText: str
    createdAt: str
    author: Author
    comments: ReviewCommentList


class ReviewList(BaseModel):
    nodes: List[Review]
    pageInfo: PageInfo


class CommentList(BaseModel):
    nodes: List[Comment]
    pageInfo: PageInfo


class LabelList(BaseModel):
    nodes: List[Label]
    pageInfo: PageInfo


class GitHubIssue(BaseModel):
    number: int
    title: str
    body: str
    createdAt: str
    author: Author
    labels: LabelList
    comments: CommentList


class GitHubPR(BaseModel):
    number: int
    title: str
    body: str
    createdAt: str
    author: Author
    reviews: ReviewList
    comments: CommentList


class Repository(BaseModel):
    issue: GitHubIssue


class PRRepository(BaseModel):
    pullRequest: GitHubPR


class Data(BaseModel):
    repository: Repository


class PRData(BaseModel):
    repository: PRRepository


class GitHubIssueResponse(BaseModel):
    data: Data


class GitHubPRResponse(BaseModel):
    data: PRData


class TaskMetadata(BaseModel):
    datetime_sourced: Optional[str]
    source_urls: List[str]
    source_issues: List[int]
    source_prs: List[int]
    ci_available_mid_run: bool
    task_alias: Optional[str]


class TaskData(BaseModel):
    task_id: str
    working_repo_url: str
    starting_commit: str
    issue_to_fix: int
    target_remote: str
    pr_data: List[GitHubPRResponse]
    issue_data: List[GitHubIssueResponse]
    live_pull_issues: list[int]
    live_pull_prs: list[int]
    repo_install_script: Optional[str]
    metadata: TaskMetadata

