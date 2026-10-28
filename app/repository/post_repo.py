"""
Repository: posts, post_daily, post_reach_breakdown.

All functions accept the row dicts produced by transform/post.py
and persist them using raw SQL via SQLAlchemy text().

Write patterns:
    - posts:                UPSERT (one row per post, latest metrics)
    - post_daily:           UPSERT on (post_id, snapshot_date)
    - post_reach_breakdown: UPSERT on (post_id, snapshot_date, action_type)
"""

from sqlalchemy import text
from db.database import get_connection
from repository.schema import ensure_schema


# ──────────────────────────────────────────────────────────────
# posts — UPSERT on (post_id)
# ──────────────────────────────────────────────────────────────

_UPSERT_POST = text("""
    INSERT INTO posts (
        post_id, account_id, media_type, sub_brand_tag,
        caption, hashtags, posted_at,
        views, reach, likes, comments, shares, saves,
        interactions_total, profile_visits
    ) VALUES (
        :post_id, :account_id, :media_type, :sub_brand_tag,
        :caption, :hashtags, :posted_at,
        :views, :reach, :likes, :comments, :shares, :saves,
        :interactions_total, :profile_visits
    )
    ON CONFLICT (post_id)
    DO UPDATE SET
        account_id         = EXCLUDED.account_id,
        media_type         = EXCLUDED.media_type,
        sub_brand_tag      = EXCLUDED.sub_brand_tag,
        caption            = EXCLUDED.caption,
        hashtags           = EXCLUDED.hashtags,
        posted_at          = EXCLUDED.posted_at,
        views              = EXCLUDED.views,
        reach              = EXCLUDED.reach,
        likes              = EXCLUDED.likes,
        comments           = EXCLUDED.comments,
        shares             = EXCLUDED.shares,
        saves              = EXCLUDED.saves,
        interactions_total = EXCLUDED.interactions_total,
        profile_visits     = EXCLUDED.profile_visits,
        last_updated_at    = now()
""")


# ──────────────────────────────────────────────────────────────
# post_daily — UPSERT on (post_id, snapshot_date)
# ──────────────────────────────────────────────────────────────

_UPSERT_POST_DAILY = text("""
    INSERT INTO post_daily (
        post_id, snapshot_date,
        views, reach, likes, comments, shares, saves,
        interactions_total, profile_visits
    ) VALUES (
        :post_id, :snapshot_date,
        :views, :reach, :likes, :comments, :shares, :saves,
        :interactions_total, :profile_visits
    )
    ON CONFLICT (post_id, snapshot_date)
    DO UPDATE SET
        views              = EXCLUDED.views,
        reach              = EXCLUDED.reach,
        likes              = EXCLUDED.likes,
        comments           = EXCLUDED.comments,
        shares             = EXCLUDED.shares,
        saves              = EXCLUDED.saves,
        interactions_total = EXCLUDED.interactions_total,
        profile_visits     = EXCLUDED.profile_visits
""")


# ──────────────────────────────────────────────────────────────
# post_reach_breakdown — UPSERT on (post_id, snapshot_date, action_type)
# ──────────────────────────────────────────────────────────────

_UPSERT_BREAKDOWN = text("""
    INSERT INTO post_reach_breakdown (
        post_id, snapshot_date, action_type, value
    ) VALUES (
        :post_id, :snapshot_date, :action_type, :value
    )
    ON CONFLICT (post_id, snapshot_date, action_type)
    DO UPDATE SET
        value = EXCLUDED.value
""")


# ──────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────

def persist_posts(transformed: dict) -> None:
    """
    Persist the output of ``transform_posts_insights()`` to the database.

    Runs as a single transaction:
      1. UPSERT rows into ``posts``         (current state)
      2. UPSERT rows into ``post_daily``    (daily snapshot)
      3. UPSERT rows into ``post_reach_breakdown``

    Parameters
    ----------
    transformed : dict
        ``{"posts": [{...}], "post_daily": [{...}], "post_reach_breakdown": [{...}]}``
    """
    ensure_schema()

    conn = get_connection()
    try:
        # 1. posts (must go first — post_daily references posts.post_id)
        for row in transformed["posts"]:
            conn.execute(_UPSERT_POST, row)

        # 2. post_daily
        for row in transformed["post_daily"]:
            conn.execute(_UPSERT_POST_DAILY, row)

        # 3. post_reach_breakdown
        for row in transformed["post_reach_breakdown"]:
            conn.execute(_UPSERT_BREAKDOWN, row)

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
