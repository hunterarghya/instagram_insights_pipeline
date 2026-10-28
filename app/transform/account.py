"""
Transform raw account-level API JSON into row dicts for the database.

Input:  output of account_service.fetch_all_account_insights(client)
Output: dict with two keys:
    - "account_daily"       → single row dict
    - "account_active_hours" → list of row dicts (one per hour, 0..23)

Derived fields computed here:
    - engagement_rate   = accounts_engaged / reach
    - bio_link_ctr      = external_link_taps / profile_visits
    - Flattened breakdown splits (views_followers, views_reels, etc.)
"""

from datetime import date


# ──────────────────────────────────────────────────────────────
# Extraction helpers
# ──────────────────────────────────────────────────────────────

def _extract_total_value(insight: dict) -> int | None:
    """
    Extract the scalar total from an insight response.

    Works with the ``total_value`` format used by account insights::

        {"data": [{"total_value": {"value": 44120}}]}
    """
    data = insight.get("data")
    if not data:
        return None
    return data[0].get("total_value", {}).get("value")


def _extract_breakdown_value(insight: dict, dimension_value: str) -> int | None:
    """
    Extract a single breakdown result from an insight response.

    Looks inside ``data[0].total_value.breakdowns[0].results`` for a result
    whose ``dimension_values`` list contains *dimension_value* and returns
    its ``value``.  Returns ``None`` if the breakdown or result is missing.
    """
    data = insight.get("data")
    if not data:
        return None
    total_value = data[0].get("total_value", {})
    breakdowns = total_value.get("breakdowns", [])
    if not breakdowns:
        return None
    for result in breakdowns[0].get("results", []):
        if dimension_value in result.get("dimension_values", []):
            return result.get("value")
    return None


def _safe_int(value, default: int = 0) -> int:
    """Try to parse *value* as int, returning *default* on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


# ──────────────────────────────────────────────────────────────
# Main transform
# ──────────────────────────────────────────────────────────────

def transform_account_insights(raw: dict) -> dict:
    """
    Reshape the combined account insights JSON into row dicts.

    Parameters
    ----------
    raw : dict
        Output of ``account_service.fetch_all_account_insights(client)``.

    Returns
    -------
    dict
        ``{"account_daily": {…}, "account_active_hours": [{…}, …]}``
    """
    today = date.today().isoformat()

    # ── account info (user fields) ────────────────────────────
    info = raw.get("account_info", {})
    account_id = _safe_int(info.get("id"), 0)
    followers = info.get("followers_count")
    following = info.get("follows_count")
    total_posts = info.get("media_count")

    # ── simple total-value insights ───────────────────────────
    reach = _extract_total_value(raw.get("reach", {}))
    views_total = _extract_total_value(raw.get("views_total", {}))
    interactions_total = _extract_total_value(raw.get("total_interactions", {}))
    accounts_engaged = _extract_total_value(raw.get("accounts_engaged", {}))

    # profile_links_taps (without breakdown) → external_link_taps
    external_link_taps = _extract_total_value(raw.get("profile_links_taps", {}))

    # profile_links_taps (with breakdown) → profile_visits (total)
    profile_visits = _extract_total_value(raw.get("profile_links_taps_by_button", {}))

    # ── views breakdown: follow_type ──────────────────────────
    views_follow = raw.get("views_by_follow_type", {})
    views_followers = _extract_breakdown_value(views_follow, "FOLLOWER")
    views_non_followers = _extract_breakdown_value(views_follow, "NON_FOLLOWER")

    # ── views breakdown: media_product_type ───────────────────
    views_media = raw.get("views_by_media_type", {})
    views_reels = _extract_breakdown_value(views_media, "REEL")
    views_stories = _extract_breakdown_value(views_media, "STORY")
    views_posts = _extract_breakdown_value(views_media, "POST")

    # ── interactions breakdown: media_product_type ────────────
    interactions_media = raw.get("interactions_by_media_type", {})
    interactions_reels = _extract_breakdown_value(interactions_media, "REEL")
    interactions_stories = _extract_breakdown_value(interactions_media, "STORY")
    interactions_posts = _extract_breakdown_value(interactions_media, "POST")

    # ── derived metrics ───────────────────────────────────────
    engagement_rate = (
        round(accounts_engaged / reach, 4)
        if accounts_engaged is not None and reach
        else None
    )
    bio_link_ctr = (
        round(external_link_taps / profile_visits, 4)
        if external_link_taps is not None and profile_visits
        else None
    )

    # ── account_daily row ─────────────────────────────────────
    account_daily = {
        "account_id": account_id,
        "snapshot_date": today,
        "followers": followers,
        "following": following,
        "total_posts": total_posts,
        "reach": reach,
        "views_total": views_total,
        "views_followers": views_followers,
        "views_non_followers": views_non_followers,
        "views_reels": views_reels,
        "views_stories": views_stories,
        "views_posts": views_posts,
        "interactions_total": interactions_total,
        "interactions_reels": interactions_reels,
        "interactions_stories": interactions_stories,
        "interactions_posts": interactions_posts,
        "accounts_engaged": accounts_engaged,
        "profile_visits": profile_visits,
        "external_link_taps": external_link_taps,
        "engagement_rate": engagement_rate,
        "bio_link_ctr": bio_link_ctr,
    }

    # ── account_active_hours rows ─────────────────────────────
    account_active_hours: list[dict] = []
    online_data = raw.get("online_followers", {}).get("data", [])
    if online_data:
        values_list = online_data[0].get("values", [])
        if values_list:
            hour_map = values_list[0].get("value", {})
            for hour_str, online_count in hour_map.items():
                account_active_hours.append({
                    "account_id": account_id,
                    "snapshot_date": today,
                    "hour_of_day": int(hour_str),
                    "online_count": online_count,
                })
            # Sort by hour for deterministic output.
            account_active_hours.sort(key=lambda r: r["hour_of_day"])

    return {
        "account_daily": account_daily,
        "account_active_hours": account_active_hours,
    }
