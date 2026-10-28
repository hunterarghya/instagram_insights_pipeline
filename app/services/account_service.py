"""
Account-level Instagram Graph API service.

Every public function hits one (or a small set of) Graph API endpoints and
returns the raw JSON response dict.  No transformation, no DB writes — that
is the job of the transform and repository layers.

Endpoints covered (from the account-insights mapping doc):
  • IG User fields      — followers_count, follows_count, media_count
  • IG User Insights    — reach, views, total_interactions, accounts_engaged,
                          profile_links_taps  (with optional breakdowns)
  • Online followers    — online_followers (period=lifetime)

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
# IG User Fields (GET /<IG_ID>?fields=…)
# ──────────────────────────────────────────────────────────────

def fetch_account_info(client: GraphClient) -> dict:
    """
    Fetch basic account-level fields in a single request.

    Returns JSON like::

        {
            "followers_count": 15234,
            "follows_count": 412,
            "media_count": 287,
            "id": "<IG_ID>"
        }
    """
    if _is_dummy():
        return {
            "followers_count": 15234,
            "follows_count": 412,
            "media_count": 287,
            "id": _DUMMY_IG_ID,
        }

    return client.get(
        f"/{_ig_id()}",
        params={"fields": "followers_count,follows_count,media_count"},
    )


# ──────────────────────────────────────────────────────────────
# IG User Insights — simple total_value metrics
#   GET /<IG_ID>/insights?metric=<M>&period=day&metric_type=total_value
# ──────────────────────────────────────────────────────────────

def _fetch_insight(client: GraphClient, metric: str, *, breakdown: str | None = None) -> dict:
    """
    Internal helper — fetch a single account insight metric.

    Parameters
    ----------
    client : GraphClient
    metric : str
        Metric name (``reach``, ``views``, ``total_interactions``, …).
    breakdown : str, optional
        Optional breakdown key (``follow_type``, ``media_product_type``,
        ``contact_button_type``).

    Returns the full JSON body (caller picks out ``data[0]``).
    """
    params: dict = {
        "metric": metric,
        "period": "day",
        "metric_type": "total_value",
    }
    if breakdown:
        params["breakdown"] = breakdown
    return client.get(f"/{_ig_id()}/insights", params=params)


def fetch_reach(client: GraphClient) -> dict:
    """
    Accounts reached (total).

    Response shape::

        {"data": [{"name": "reach", "total_value": {"value": 44120}, …}]}
    """
    if _is_dummy():
        return {
            "data": [{
                "name": "reach",
                "period": "day",
                "total_value": {"value": 44120},
                "id": f"{_DUMMY_IG_ID}/insights/reach/day",
            }],
        }

    return _fetch_insight(client, "reach")


def fetch_views_total(client: GraphClient) -> dict:
    """Total views (no breakdown)."""
    if _is_dummy():
        return {
            "data": [{
                "name": "views",
                "period": "day",
                "total_value": {"value": 101230},
                "id": f"{_DUMMY_IG_ID}/insights/views/day",
            }],
        }

    return _fetch_insight(client, "views")


def fetch_views_by_follow_type(client: GraphClient) -> dict:
    """Views split by FOLLOWER / NON_FOLLOWER."""
    if _is_dummy():
        return {
            "data": [{
                "name": "views",
                "period": "day",
                "total_value": {
                    "value": 101230,
                    "breakdowns": [{
                        "dimension_keys": ["follow_type"],
                        "results": [
                            {"dimension_values": ["FOLLOWER"], "value": 68200},
                            {"dimension_values": ["NON_FOLLOWER"], "value": 33030},
                        ],
                    }],
                },
                "id": f"{_DUMMY_IG_ID}/insights/views/day",
            }],
        }

    return _fetch_insight(client, "views", breakdown="follow_type")


def fetch_views_by_media_type(client: GraphClient) -> dict:
    """Views split by content type (REEL / STORY / POST)."""
    if _is_dummy():
        return {
            "data": [{
                "name": "views",
                "period": "day",
                "total_value": {
                    "value": 101230,
                    "breakdowns": [{
                        "dimension_keys": ["media_product_type"],
                        "results": [
                            {"dimension_values": ["REEL"], "value": 52900},
                            {"dimension_values": ["STORY"], "value": 28600},
                            {"dimension_values": ["POST"], "value": 19730},
                        ],
                    }],
                },
                "id": f"{_DUMMY_IG_ID}/insights/views/day",
            }],
        }

    return _fetch_insight(client, "views", breakdown="media_product_type")


def fetch_total_interactions(client: GraphClient) -> dict:
    """Total interactions (no breakdown)."""
    if _is_dummy():
        return {
            "data": [{
                "name": "total_interactions",
                "period": "day",
                "total_value": {"value": 5540},
                "id": f"{_DUMMY_IG_ID}/insights/total_interactions/day",
            }],
        }

    return _fetch_insight(client, "total_interactions")


def fetch_interactions_by_media_type(client: GraphClient) -> dict:
    """Interactions split by content type (REEL / STORY / POST)."""
    if _is_dummy():
        return {
            "data": [{
                "name": "total_interactions",
                "period": "day",
                "total_value": {
                    "value": 5540,
                    "breakdowns": [{
                        "dimension_keys": ["media_product_type"],
                        "results": [
                            {"dimension_values": ["REEL"], "value": 3010},
                            {"dimension_values": ["STORY"], "value": 1470},
                            {"dimension_values": ["POST"], "value": 1060},
                        ],
                    }],
                },
                "id": f"{_DUMMY_IG_ID}/insights/total_interactions/day",
            }],
        }

    return _fetch_insight(client, "total_interactions", breakdown="media_product_type")


def fetch_accounts_engaged(client: GraphClient) -> dict:
    """Accounts engaged (total)."""
    if _is_dummy():
        return {
            "data": [{
                "name": "accounts_engaged",
                "period": "day",
                "total_value": {"value": 4012},
                "id": f"{_DUMMY_IG_ID}/insights/accounts_engaged/day",
            }],
        }

    return _fetch_insight(client, "accounts_engaged")


def fetch_profile_links_taps(client: GraphClient) -> dict:
    """
    Profile link taps (total).

    Covers both *profile visits* proxy and *external link taps*.
    """
    if _is_dummy():
        return {
            "data": [{
                "name": "profile_links_taps",
                "period": "day",
                "total_value": {"value": 201},
                "id": f"{_DUMMY_IG_ID}/insights/profile_links_taps/day",
            }],
        }

    return _fetch_insight(client, "profile_links_taps")


def fetch_profile_links_taps_by_button_type(client: GraphClient) -> dict:
    """Profile link taps split by contact_button_type (TEXT / CALL / …)."""
    if _is_dummy():
        return {
            "data": [{
                "name": "profile_links_taps",
                "period": "day",
                "total_value": {
                    "value": 1287,
                    "breakdowns": [{
                        "dimension_keys": ["contact_button_type"],
                        "results": [
                            {"dimension_values": ["TEXT"], "value": 1100},
                            {"dimension_values": ["CALL"], "value": 187},
                        ],
                    }],
                },
                "id": f"{_DUMMY_IG_ID}/insights/profile_links_taps/day",
            }],
        }

    return _fetch_insight(client, "profile_links_taps", breakdown="contact_button_type")


# ──────────────────────────────────────────────────────────────
# Online Followers (most active times)
#   GET /<IG_ID>/insights?metric=online_followers&period=lifetime
# ──────────────────────────────────────────────────────────────

def fetch_online_followers(client: GraphClient) -> dict:
    """
    Followers online by hour of day.

    Response shape::

        {"data": [{
            "name": "online_followers",
            "period": "lifetime",
            "values": [{"value": {"0": 320, "1": 210, …, "23": 1480},
                         "end_time": "2026-07-17T07:00:00+0000"}]
        }]}
    """
    if _is_dummy():
        return {
            "data": [{
                "name": "online_followers",
                "period": "lifetime",
                "values": [{
                    "value": {
                        "0": 320, "1": 210, "2": 150, "3": 110, "4": 95,
                        "5": 130, "6": 280, "7": 520, "8": 890, "9": 1200,
                        "10": 1450, "11": 1580, "12": 1620, "13": 1540,
                        "14": 1380, "15": 1250, "16": 1400, "17": 1650,
                        "18": 2340, "19": 2510, "20": 2280, "21": 2050,
                        "22": 1680, "23": 1480,
                    },
                    "end_time": "2026-07-17T07:00:00+0000",
                }],
            }],
        }

    return client.get(
        f"/{_ig_id()}/insights",
        params={
            "metric": "online_followers",
            "period": "lifetime",
        },
    )


# ──────────────────────────────────────────────────────────────
# Convenience: fetch everything in one call
# ──────────────────────────────────────────────────────────────

def fetch_all_account_insights(client: GraphClient) -> dict:
    """
    Convenience wrapper that fetches **all** account-level data points
    and returns them in a single dict keyed by logical name.

    Returns::

        {
            "account_info":                 {…},
            "reach":                        {…},
            "views_total":                  {…},
            "views_by_follow_type":         {…},
            "views_by_media_type":          {…},
            "total_interactions":           {…},
            "interactions_by_media_type":   {…},
            "accounts_engaged":            {…},
            "profile_links_taps":          {…},
            "profile_links_taps_by_button": {…},
            "online_followers":            {…},
        }
    """
    return {
        "account_info":                  fetch_account_info(client),
        "reach":                         fetch_reach(client),
        "views_total":                   fetch_views_total(client),
        "views_by_follow_type":          fetch_views_by_follow_type(client),
        "views_by_media_type":           fetch_views_by_media_type(client),
        "total_interactions":            fetch_total_interactions(client),
        "interactions_by_media_type":    fetch_interactions_by_media_type(client),
        "accounts_engaged":             fetch_accounts_engaged(client),
        "profile_links_taps":           fetch_profile_links_taps(client),
        "profile_links_taps_by_button": fetch_profile_links_taps_by_button_type(client),
        "online_followers":             fetch_online_followers(client),
    }
