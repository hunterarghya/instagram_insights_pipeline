"""
Post-level Instagram Graph API service.

Every public function hits one Graph API endpoint and returns the raw JSON
response dict.  No transformation, no DB writes.

Endpoints covered (from the post-level-insights mapping doc):
  • Media fields         — id, media_type, media_product_type, caption,
                           permalink, timestamp, like_count, comments_count,
                           saved_count, shares_count
  • Media insights       — views, reach, total_interactions, profile_activity
  • User media edge      — GET /<IG_ID>/media  (paginated list of media ids)

When DUMMY_SWITCH=1 in .env, every function returns a realistic dummy JSON
response without hitting the API.
"""

from clients.graph_client import GraphClient
from config.settings import get_settings


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _ig_id() -> str:
    """Return the configured Instagram account id."""
    return get_settings().instagram.account_id


def _is_dummy() -> bool:
    """Return True when the dummy switch is active."""
    return get_settings().dummy_switch


# ──────────────────────────────────────────────────────────────
# Dummy post data — three posts of different types
# ──────────────────────────────────────────────────────────────

_DUMMY_POSTS = {
    "17851000001": {
        "fields": {
            "id": "17851000001",
            "media_type": "VIDEO",
            "media_product_type": "REELS",
            "caption": "Summer drop is live!  #summerdrop #newcollection",
            "permalink": "https://www.instagram.com/p/dummy_reel_001/",
            "timestamp": "2026-07-10T14:30:00+0000",
            "like_count": 75,
            "comments_count": 12,
            "saved_count": 22,
            "shares_count": 8,
        },
        "views": 41200,
        "reach": 9800,
        "total_interactions": 117,
        "profile_activity": {
            "total": 4,
            "breakdowns": [
                {"dimension_values": ["bio_link_clicked"], "value": 1},
                {"dimension_values": ["direction"], "value": 1},
                {"dimension_values": ["call"], "value": 1},
                {"dimension_values": ["text"], "value": 1},
            ],
        },
    },
    "17851000002": {
        "fields": {
            "id": "17851000002",
            "media_type": "IMAGE",
            "media_product_type": "POST",
            "caption": "Behind the scenes  #travel #foodie",
            "permalink": "https://www.instagram.com/p/dummy_image_002/",
            "timestamp": "2026-07-12T10:15:00+0000",
            "like_count": 142,
            "comments_count": 28,
            "saved_count": 35,
            "shares_count": 14,
        },
        "views": 18500,
        "reach": 6200,
        "total_interactions": 219,
        "profile_activity": {
            "total": 7,
            "breakdowns": [
                {"dimension_values": ["bio_link_clicked"], "value": 3},
                {"dimension_values": ["call"], "value": 2},
                {"dimension_values": ["text"], "value": 2},
            ],
        },
    },
    "17851000003": {
        "fields": {
            "id": "17851000003",
            "media_type": "CAROUSEL_ALBUM",
            "media_product_type": "POST",
            "caption": "New menu alert Swipe to see all items! #menu #launch",
            "permalink": "https://www.instagram.com/p/dummy_carousel_003/",
            "timestamp": "2026-07-15T18:00:00+0000",
            "like_count": 210,
            "comments_count": 45,
            "saved_count": 58,
            "shares_count": 31,
        },
        "views": 55400,
        "reach": 14300,
        "total_interactions": 344,
        "profile_activity": {
            "total": 12,
            "breakdowns": [
                {"dimension_values": ["bio_link_clicked"], "value": 5},
                {"dimension_values": ["direction"], "value": 3},
                {"dimension_values": ["call"], "value": 2},
                {"dimension_values": ["text"], "value": 2},
            ],
        },
    },
}

_DUMMY_POST_IDS = list(_DUMMY_POSTS.keys())


def _get_dummy_post(media_id: str) -> dict:
    """Return dummy data for a media id, falling back to the first post."""
    return _DUMMY_POSTS.get(media_id, _DUMMY_POSTS[_DUMMY_POST_IDS[0]])


# ──────────────────────────────────────────────────────────────
# List all media ids (paginated)
#   GET /<IG_ID>/media?fields=id&limit=50
# ──────────────────────────────────────────────────────────────

def fetch_media_ids(client: GraphClient, *, limit: int = 50) -> list[dict]:
    """
    Return **all** media ids for the configured account, handling pagination.

    Each item is a dict like ``{"id": "17851000001"}``.
    The function follows ``paging.next`` until exhausted.

    Parameters
    ----------
    client : GraphClient
    limit : int
        Page size per request (max 100, default 50).
    """
    if _is_dummy():
        return [{"id": pid} for pid in _DUMMY_POST_IDS]

    all_media: list[dict] = []

    response = client.get(
        f"/{_ig_id()}/media",
        params={"fields": "id", "limit": str(limit)},
    )
    all_media.extend(response.get("data", []))

    # Follow pagination cursors.
    while "paging" in response and "next" in response["paging"]:
        next_url = response["paging"]["next"]
        # The next URL is a full URL; we use the client's underlying httpx
        # directly (token is already in the URL from the API).
        import httpx as _httpx
        resp = _httpx.get(next_url, timeout=30.0)
        resp.raise_for_status()
        response = resp.json()
        all_media.extend(response.get("data", []))

    return all_media


# ──────────────────────────────────────────────────────────────
# Media fields (GET /<MEDIA_ID>?fields=…)
# ──────────────────────────────────────────────────────────────

_POST_FIELDS = (
    "id,"
    "media_type,"
    "media_product_type,"
    "caption,"
    "permalink,"
    "timestamp,"
    "like_count,"
    "comments_count,"
    "saved_count,"
    "shares_count"
)


def fetch_post_fields(client: GraphClient, media_id: str) -> dict:
    """
    Fetch static + engagement fields for a single post.

    Returns JSON like::

        {
            "id": "17851000001",
            "media_type": "VIDEO",
            "media_product_type": "REELS",
            "caption": "Summer drop is live! #summerdrop",
            "permalink": "https://www.instagram.com/p/…",
            "timestamp": "2026-07-10T14:30:00+0000",
            "like_count": 75,
            "comments_count": 12,
            "saved_count": 22,
            "shares_count": 8
        }
    """
    if _is_dummy():
        return _get_dummy_post(media_id)["fields"]

    return client.get(f"/{media_id}", params={"fields": _POST_FIELDS})


# ──────────────────────────────────────────────────────────────
# Media insights (GET /<MEDIA_ID>/insights?metric=…)
# ──────────────────────────────────────────────────────────────

def fetch_post_views(client: GraphClient, media_id: str) -> dict:
    """
    Views / plays for a single post.

    Response shape::

        {"data": [{"name": "views", "values": [{"value": 41200}], …}]}
    """
    if _is_dummy():
        dummy = _get_dummy_post(media_id)
        return {
            "data": [{
                "name": "views",
                "period": "lifetime",
                "values": [{"value": dummy["views"]}],
                "id": f"{media_id}/insights/views/lifetime",
            }],
        }

    return client.get(f"/{media_id}/insights", params={"metric": "views"})


def fetch_post_reach(client: GraphClient, media_id: str) -> dict:
    """Accounts reached for a single post."""
    if _is_dummy():
        dummy = _get_dummy_post(media_id)
        return {
            "data": [{
                "name": "reach",
                "period": "lifetime",
                "values": [{"value": dummy["reach"]}],
                "id": f"{media_id}/insights/reach/lifetime",
            }],
        }

    return client.get(f"/{media_id}/insights", params={"metric": "reach"})


def fetch_post_total_interactions(client: GraphClient, media_id: str) -> dict:
    """Total interactions for a single post."""
    if _is_dummy():
        dummy = _get_dummy_post(media_id)
        return {
            "data": [{
                "name": "total_interactions",
                "period": "lifetime",
                "values": [{"value": dummy["total_interactions"]}],
                "id": f"{media_id}/insights/total_interactions/lifetime",
            }],
        }

    return client.get(
        f"/{media_id}/insights",
        params={"metric": "total_interactions"},
    )


def fetch_post_profile_activity(client: GraphClient, media_id: str) -> dict:
    """
    Profile activity from a single post, broken down by action_type.

    Breakdown values: bio_link_clicked, call, email, direction, text, other.

    Response shape::

        {"data": [{
            "name": "profile_activity",
            "total_value": {
                "value": 4,
                "breakdowns": [{
                    "dimension_keys": ["action_type"],
                    "results": [
                        {"dimension_values": ["bio_link_clicked"], "value": 1},
                        …
                    ]
                }]
            }
        }]}
    """
    if _is_dummy():
        dummy = _get_dummy_post(media_id)
        pa = dummy["profile_activity"]
        return {
            "data": [{
                "name": "profile_activity",
                "period": "lifetime",
                "total_value": {
                    "value": pa["total"],
                    "breakdowns": [{
                        "dimension_keys": ["action_type"],
                        "results": pa["breakdowns"],
                    }],
                },
                "id": f"{media_id}/insights/profile_activity/lifetime",
            }],
        }

    return client.get(
        f"/{media_id}/insights",
        params={"metric": "profile_activity", "breakdown": "action_type"},
    )


# ──────────────────────────────────────────────────────────────
# Convenience: fetch all insights for a single post
# ──────────────────────────────────────────────────────────────

def fetch_all_post_insights(client: GraphClient, media_id: str) -> dict:
    """
    Convenience wrapper — fetches fields + all insight metrics for one post.

    Returns::

        {
            "fields":            {…},   # media fields (type, caption, counts, …)
            "views":             {…},   # media insights: views
            "reach":             {…},   # media insights: reach
            "total_interactions": {…},  # media insights: total_interactions
            "profile_activity":  {…},   # media insights: profile_activity by action_type
        }
    """
    return {
        "fields":             fetch_post_fields(client, media_id),
        "views":              fetch_post_views(client, media_id),
        "reach":              fetch_post_reach(client, media_id),
        "total_interactions":  fetch_post_total_interactions(client, media_id),
        "profile_activity":   fetch_post_profile_activity(client, media_id),
    }


def fetch_all_posts_insights(client: GraphClient, *, limit: int = 50) -> list[dict]:
    """
    Convenience wrapper — fetches media ids then retrieves full insights
    for every post.

    Returns a list of dicts, one per post, each shaped like the output of
    :func:`fetch_all_post_insights`.
    """
    media_items = fetch_media_ids(client, limit=limit)
    results: list[dict] = []
    for item in media_items:
        media_id = item["id"]
        results.append(fetch_all_post_insights(client, media_id))
    return results
