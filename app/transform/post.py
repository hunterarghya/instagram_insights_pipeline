"""
Transform raw post-level API JSON into row dicts for the database.

Input:  output of post_service.fetch_all_posts_insights(client)
        (a list of dicts, one per post)
Output: dict with three keys:
    - "posts"                → list of row dicts (UPSERT)
    - "post_daily"           → list of row dicts (APPEND)
    - "post_reach_breakdown" → list of row dicts (APPEND)

Derived fields computed here:
    - hashtags      — regex-parsed from caption
    - sub_brand_tag — keyword/pattern match on caption
"""

import re
from datetime import date


# ──────────────────────────────────────────────────────────────
# Sub-brand keyword map
# ──────────────────────────────────────────────────────────────
# Maps lowercase keywords (found in caption text or hashtags) to
# a sub-brand tag.  First match wins.  Extend this dict with your
# own business rules.

SUB_BRAND_MAP: dict[str, str] = {
    "summerdrop": "summer_line",
    "summer line": "summer_line",
    "newcollection": "new_collection",
    "new collection": "new_collection",
    "menu": "menu_launch",
    "launch": "menu_launch",
    "bts": "behind_the_scenes",
    "behind the scenes": "behind_the_scenes",
}


# ──────────────────────────────────────────────────────────────
# Parsing helpers
# ──────────────────────────────────────────────────────────────

def _parse_hashtags(caption: str | None) -> list[str]:
    """
    Extract hashtags from a caption string.

    Returns a deduplicated, lowercased list preserving first-seen order.
    Example: ``"Summer! #SummerDrop #newcollection #summerdrop"``
             → ``["summerdrop", "newcollection"]``
    """
    if not caption:
        return []
    tags = re.findall(r"#(\w+)", caption)
    seen: set[str] = set()
    result: list[str] = []
    for tag in tags:
        lower = tag.lower()
        if lower not in seen:
            seen.add(lower)
            result.append(lower)
    return result


def _derive_sub_brand_tag(caption: str | None) -> str | None:
    """
    Derive a sub-brand tag by matching the caption against
    :data:`SUB_BRAND_MAP`.  First match wins.  Returns ``None``
    if no match.
    """
    if not caption:
        return None
    lower_caption = caption.lower()
    for keyword, tag in SUB_BRAND_MAP.items():
        if keyword in lower_caption:
            return tag
    return None


# ──────────────────────────────────────────────────────────────
# Insight extraction helpers
# ──────────────────────────────────────────────────────────────

def _extract_insight_value(insight: dict) -> int | None:
    """
    Extract the scalar value from a media insight response.

    Handles both response shapes the API uses:
      - ``values`` format:      ``data[0].values[0].value``
      - ``total_value`` format: ``data[0].total_value.value``
    """
    data = insight.get("data")
    if not data:
        return None
    entry = data[0]
    # Try "values" format first (views, reach, total_interactions).
    values = entry.get("values")
    if values:
        return values[0].get("value")
    # Fall back to "total_value" format (profile_activity).
    total_value = entry.get("total_value")
    if total_value:
        return total_value.get("value")
    return None


def _extract_action_breakdowns(insight: dict) -> list[dict]:
    """
    Extract ``action_type`` breakdown rows from a ``profile_activity``
    insight response.

    Returns a list of ``{"action_type": str, "value": int}`` dicts.
    """
    data = insight.get("data")
    if not data:
        return []
    total_value = data[0].get("total_value", {})
    breakdowns = total_value.get("breakdowns", [])
    if not breakdowns:
        return []

    rows: list[dict] = []
    for result in breakdowns[0].get("results", []):
        dim_values = result.get("dimension_values", [])
        action_type = dim_values[0] if dim_values else "unknown"
        rows.append({
            "action_type": action_type,
            "value": result.get("value"),
        })
    return rows


def _safe_int(value, default: int = 0) -> int:
    """Try to parse *value* as int, returning *default* on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


# ──────────────────────────────────────────────────────────────
# Main transform
# ──────────────────────────────────────────────────────────────

def transform_posts_insights(raw_posts: list[dict], account_id: int) -> dict:
    """
    Reshape the combined post insights JSON into row dicts.

    Parameters
    ----------
    raw_posts : list[dict]
        Output of ``post_service.fetch_all_posts_insights(client)``.
        Each element is the output of ``fetch_all_post_insights`` for one post.
    account_id : int
        The IG account id that owns these posts.

    Returns
    -------
    dict
        ``{"posts": [{…}], "post_daily": [{…}], "post_reach_breakdown": [{…}]}``
    """
    today = date.today().isoformat()

    posts_rows: list[dict] = []
    daily_rows: list[dict] = []
    breakdown_rows: list[dict] = []

    for post_raw in raw_posts:
        fields = post_raw.get("fields", {})

        # ── identifiers & static fields ───────────────────────
        post_id = _safe_int(fields.get("id"), 0)
        caption = fields.get("caption")
        hashtags = _parse_hashtags(caption)
        sub_brand_tag = _derive_sub_brand_tag(caption)

        # ── metric values ─────────────────────────────────────
        views = _extract_insight_value(post_raw.get("views", {}))
        reach = _extract_insight_value(post_raw.get("reach", {}))
        total_interactions = _extract_insight_value(
            post_raw.get("total_interactions", {})
        )
        profile_visits = _extract_insight_value(
            post_raw.get("profile_activity", {})
        )

        # likes, comments, shares, saves come from the fields response.
        likes = fields.get("like_count")
        comments = fields.get("comments_count")
        shares = fields.get("shares_count")
        saves = fields.get("saved_count")

        # ── posts row (UPSERT) ────────────────────────────────
        posts_rows.append({
            "post_id": post_id,
            "account_id": account_id,
            "media_type": fields.get("media_type"),
            "sub_brand_tag": sub_brand_tag,
            "caption": caption,
            "hashtags": hashtags,
            "posted_at": fields.get("timestamp"),
            "views": views,
            "reach": reach,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "saves": saves,
            "interactions_total": total_interactions,
            "profile_visits": profile_visits,
        })

        # ── post_daily row (APPEND) ───────────────────────────
        daily_rows.append({
            "post_id": post_id,
            "snapshot_date": today,
            "views": views,
            "reach": reach,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "saves": saves,
            "interactions_total": total_interactions,
            "profile_visits": profile_visits,
        })

        # ── post_reach_breakdown rows (APPEND) ────────────────
        action_breakdowns = _extract_action_breakdowns(
            post_raw.get("profile_activity", {})
        )
        for bd in action_breakdowns:
            breakdown_rows.append({
                "post_id": post_id,
                "snapshot_date": today,
                "action_type": bd["action_type"],
                "value": bd["value"],
            })

    return {
        "posts": posts_rows,
        "post_daily": daily_rows,
        "post_reach_breakdown": breakdown_rows,
    }
