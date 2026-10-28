"""
Transform raw collaborator API JSON into row dicts for the database.

Input:  list of (post_id, enriched_collaborators) tuples, where each
        enriched_collaborators list is the output of
        collaborator_service.fetch_post_collaborators_with_details().
Output: dict with two keys:
    - "collaborators"       → list of row dicts (UPSERT, deduplicated)
    - "post_collaborators"  → list of row dicts (link rows)

Derived fields:
    - followers_count and account_type come from the Business Discovery
      call (secondary API fetch), merged in by the service layer.
"""


def _safe_int(value, default: int = 0) -> int:
    """Try to parse *value* as int, returning *default* on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def transform_collaborators(
    posts_with_collabs: list[tuple[int, list[dict]]],
) -> dict:
    """
    Reshape collaborator edge + Business Discovery JSON into row dicts.

    Parameters
    ----------
    posts_with_collabs : list[tuple[int, list[dict]]]
        Each tuple is ``(post_id, enriched_collaborators)``.
        ``enriched_collaborators`` is the output of
        ``collaborator_service.fetch_post_collaborators_with_details()``,
        i.e. a list of dicts like::

            {
                "edge":    {"id": "…", "username": "…", "invite_status": "…"},
                "details": {"business_discovery": {…}, "id": "…"}
            }

    Returns
    -------
    dict
        ``{"collaborators": [{…}], "post_collaborators": [{…}]}``
    """
    # Use a dict keyed by collaborator_id to deduplicate.
    # If the same collaborator appears on multiple posts, the latest
    # details win (they should be identical anyway).
    collab_map: dict[int, dict] = {}
    link_rows: list[dict] = []

    for post_id, enriched_list in posts_with_collabs:
        for entry in enriched_list:
            edge = entry.get("edge", {})
            details = entry.get("details") or {}

            collaborator_id = _safe_int(edge.get("id"), 0)
            if collaborator_id == 0:
                continue  # skip malformed entries

            username = edge.get("username")
            invite_status = edge.get("invite_status")

            # Extract Business Discovery fields (may be absent or errored).
            biz = details.get("business_discovery", {})
            followers_count = biz.get("followers_count")

            # ── collaborator row (UPSERT) ─────────────────────
            collab_map[collaborator_id] = {
                "collaborator_id": collaborator_id,
                "username": username,
                "followers_count": followers_count,
                "invite_status": invite_status,
            }

            # ── post_collaborators link row ───────────────────
            link_rows.append({
                "post_id": post_id,
                "collaborator_id": collaborator_id,
            })

    return {
        "collaborators": list(collab_map.values()),
        "post_collaborators": link_rows,
    }
