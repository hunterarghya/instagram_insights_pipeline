"""
Sync router — trigger Instagram data sync via HTTP.

Endpoints:
    POST /sync/account        — sync account-level insights
    POST /sync/posts          — sync post-level insights
    POST /sync/collaborators  — sync collaborator data
    POST /sync/all            — run all three syncs in sequence
"""

from fastapi import APIRouter
from jobs.sync_account import sync_account
from jobs.sync_posts import sync_posts
from jobs.sync_collaborators import sync_collaborators

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/account")
def trigger_sync_account():
    """
    Fetch account-level insights from Instagram, transform into
    row dicts, and return the result.
    """
    result = sync_account()
    return {"status": "ok", "data": result}


@router.post("/posts")
def trigger_sync_posts():
    """
    Fetch post-level insights for all posts, transform into
    row dicts, and return the result.
    """
    result = sync_posts()
    return {"status": "ok", "data": result}


@router.post("/collaborators")
def trigger_sync_collaborators():
    """
    Fetch collaborator data for all posts, transform into
    row dicts, and return the result.
    """
    result = sync_collaborators()
    return {"status": "ok", "data": result}


@router.post("/all")
def trigger_sync_all():
    """
    Run all three syncs in sequence: account, posts, collaborators.
    Returns the combined result.
    """
    account_result = sync_account()
    posts_result = sync_posts()
    collabs_result = sync_collaborators()

    return {
        "status": "ok",
        "data": {
            "account": account_result,
            "posts": posts_result,
            "collaborators": collabs_result,
        },
    }
