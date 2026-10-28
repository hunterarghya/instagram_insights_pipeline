"""
Orchestrator: sync post-level insights.

Flow:  service -> transform -> repository
"""

from clients.graph_client import GraphClient
from services import account_service, post_service
from transform.post import transform_posts_insights
from repository.post_repo import persist_posts


def _safe_int(value, default: int = 0) -> int:
    """Try to parse *value* as int, returning *default* on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def sync_posts() -> dict:
    """
    Fetch all post-level insights from Instagram, transform
    them into row dicts, and persist to the database.

    Returns
    -------
    dict
        ``{"posts": [{...}], "post_daily": [{...}], "post_reach_breakdown": [{...}]}``
    """
    with GraphClient() as client:
        account_info = account_service.fetch_account_info(client)
        account_id = _safe_int(account_info.get("id"), 0)

        raw_posts = post_service.fetch_all_posts_insights(client)

    transformed = transform_posts_insights(raw_posts, account_id)

    persist_posts(transformed)

    return transformed
