"""
Collaborator-level Instagram Graph API service.

Every public function hits one Graph API endpoint and returns the raw JSON
response dict.  No transformation, no DB writes.

Endpoints covered (from the post-level-insights mapping doc):
  • Collaborators edge       — GET /<MEDIA_ID>/collaborators
  • Business Discovery       — GET /<IG_ID>?fields=business_discovery.username(<USERNAME>){…}

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


_DUMMY_IG_ID = "DUMMY_IG_ID"


# ──────────────────────────────────────────────────────────────
# Dummy collaborator data
# ──────────────────────────────────────────────────────────────

# Which dummy posts have which collaborators (keyed by media_id).
_DUMMY_POST_COLLABORATORS = {
    "17851000001": [
        {"id": "17841499001", "username": "fashion.influencer", "invite_status": "accepted"},
    ],
    "17851000002": [
        {"id": "17841499002", "username": "foodie.blogger", "invite_status": "accepted"},
        {"id": "17841499003", "username": "chef.ramsay.fan", "invite_status": "accepted"},
    ],
    "17851000003": [],  # no collaborators on this post
}

# Business Discovery details per collaborator username.
_DUMMY_COLLABORATOR_DETAILS = {
    "fashion.influencer": {
        "business_discovery": {
            "followers_count": 254000,
            "media_count": 980,
            "id": "17841499001",
            "name": "Fashion Influencer",
            "username": "fashion.influencer",
        },
        "id": _DUMMY_IG_ID,
    },
    "foodie.blogger": {
        "business_discovery": {
            "followers_count": 87500,
            "media_count": 1240,
            "id": "17841499002",
            "name": "Foodie Blogger",
            "username": "foodie.blogger",
        },
        "id": _DUMMY_IG_ID,
    },
    "chef.ramsay.fan": {
        "business_discovery": {
            "followers_count": 42300,
            "media_count": 560,
            "id": "17841499003",
            "name": "Chef Ramsay Fan Page",
            "username": "chef.ramsay.fan",
        },
        "id": _DUMMY_IG_ID,
    },
}


# ──────────────────────────────────────────────────────────────
# Collaborators Edge
#   GET /<MEDIA_ID>/collaborators
# ──────────────────────────────────────────────────────────────

def fetch_post_collaborators(client: GraphClient, media_id: str) -> dict:
    """
    Fetch the list of collaborators on a single post.

    Returns JSON like::

        {
            "data": [
                {
                    "id": "17841499001",
                    "username": "fashion.influencer",
                    "invite_status": "accepted"
                }
            ]
        }

    Returns ``{"data": []}`` if the post has no collaborators.
    """
    if _is_dummy():
        collabs = _DUMMY_POST_COLLABORATORS.get(media_id, [])
        return {"data": collabs}

    return client.get(f"/{media_id}/collaborators")


# ──────────────────────────────────────────────────────────────
# Business Discovery (collaborator details by username)
#   GET /<IG_ID>?fields=business_discovery.username(<USERNAME>){…}
# ──────────────────────────────────────────────────────────────

def fetch_collaborator_details(client: GraphClient, username: str) -> dict:
    """
    Fetch public profile details for a collaborator via Business Discovery.

    Parameters
    ----------
    client : GraphClient
    username : str
        The collaborator's Instagram handle (without ``@``).

    Returns JSON like::

        {
            "business_discovery": {
                "followers_count": 254000,
                "media_count": 980,
                "id": "17841499001"
            },
            "id": "<IG_ID>"
        }

    Raises
    ------
    GraphAPIError
        If the username is invalid or the account is private /
        not a business/creator account.
    """
    if _is_dummy():
        if username in _DUMMY_COLLABORATOR_DETAILS:
            return _DUMMY_COLLABORATOR_DETAILS[username]
        # Simulate a "not found" response for unknown usernames.
        return {
            "business_discovery": {
                "followers_count": 0,
                "media_count": 0,
                "id": "0",
                "name": username,
                "username": username,
            },
            "id": _DUMMY_IG_ID,
        }

    fields = (
        f"business_discovery.username({username})"
        f"{{followers_count,media_count,ig_id,name,username}}"
    )
    return client.get(f"/{_ig_id()}", params={"fields": fields})


# ──────────────────────────────────────────────────────────────
# Convenience: fetch collaborators + details for a single post
# ──────────────────────────────────────────────────────────────

def fetch_post_collaborators_with_details(
    client: GraphClient, media_id: str
) -> list[dict]:
    """
    For a single post, fetch the collaborators edge and then enrich each
    collaborator with Business Discovery details.

    Returns a list of dicts, one per collaborator::

        [
            {
                "edge": {"id": "…", "username": "…", "invite_status": "accepted"},
                "details": {"business_discovery": {…}, "id": "…"}
            },
            …
        ]

    If Business Discovery fails for a collaborator (e.g. private account),
    the ``"details"`` key will contain the error dict instead of raising.
    """
    from clients.graph_client import GraphAPIError

    edge_response = fetch_post_collaborators(client, media_id)
    collaborators = edge_response.get("data", [])

    enriched: list[dict] = []
    for collab in collaborators:
        username = collab.get("username")
        entry: dict = {"edge": collab, "details": None}
        if username:
            try:
                entry["details"] = fetch_collaborator_details(client, username)
            except GraphAPIError as exc:
                # Store the error body so the transform layer can decide
                # whether to skip or log it.
                entry["details"] = {"error": exc.body, "status_code": exc.status_code}
        enriched.append(entry)

    return enriched
