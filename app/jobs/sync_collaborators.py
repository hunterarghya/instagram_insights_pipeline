"""
Orchestrator: sync collaborator data.

Flow:  service -> transform -> repository
"""

from clients.graph_client import GraphClient
from services import post_service, collaborator_service
from transform.collaborator import transform_collaborators
from repository.collaborator_repo import persist_collaborators


def _safe_int(value, default: int = 0) -> int:
    """Try to parse *value* as int, returning *default* on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def sync_collaborators() -> dict:
    """
    For every post, fetch collaborators and enrich with Business Discovery,
    then transform and persist to the database.

    Returns
    -------
    dict
        ``{"collaborators": [{...}], "post_collaborators": [{...}]}``
    """
    with GraphClient() as client:
        media_items = post_service.fetch_media_ids(client)

        posts_with_collabs: list[tuple[int, list[dict]]] = []
        for item in media_items:
            media_id = item["id"]
            enriched = collaborator_service.fetch_post_collaborators_with_details(
                client, media_id
            )
            posts_with_collabs.append((_safe_int(media_id), enriched))

    transformed = transform_collaborators(posts_with_collabs)

    persist_collaborators(transformed)

    return transformed
