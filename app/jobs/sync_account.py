"""
Orchestrator: sync account-level insights.

Flow:  service -> transform -> repository
"""

from clients.graph_client import GraphClient
from services import account_service
from transform.account import transform_account_insights
from repository.account_repo import persist_account


def sync_account() -> dict:
    """
    Fetch all account-level insights from Instagram, transform
    them into row dicts, and persist to the database.

    Returns
    -------
    dict
        ``{"account_daily": {...}, "account_active_hours": [{...}, ...]}``
    """
    with GraphClient() as client:
        raw = account_service.fetch_all_account_insights(client)

    transformed = transform_account_insights(raw)

    persist_account(transformed)

    return transformed
