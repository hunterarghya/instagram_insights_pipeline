"""
Repository: account_daily + account_active_hours.

All functions accept the row dicts produced by transform/account.py
and persist them using raw SQL via SQLAlchemy text().

Write patterns:
    - account_daily:        UPSERT (one row per account per day)
    - account_active_hours: UPSERT (one row per account/day/hour)
"""

from sqlalchemy import text
from db.database import get_connection
from repository.schema import ensure_schema


# ──────────────────────────────────────────────────────────────
# account_daily — UPSERT on (account_id, snapshot_date)
# ──────────────────────────────────────────────────────────────

_UPSERT_ACCOUNT_DAILY = text("""
    INSERT INTO account_daily (
        account_id, snapshot_date,
        followers, following, total_posts, reach,
        views_total, views_followers, views_non_followers,
        views_reels, views_stories, views_posts,
        interactions_total,
        interactions_reels, interactions_stories, interactions_posts,
        accounts_engaged, profile_visits, external_link_taps,
        engagement_rate, bio_link_ctr
    ) VALUES (
        :account_id, :snapshot_date,
        :followers, :following, :total_posts, :reach,
        :views_total, :views_followers, :views_non_followers,
        :views_reels, :views_stories, :views_posts,
        :interactions_total,
        :interactions_reels, :interactions_stories, :interactions_posts,
        :accounts_engaged, :profile_visits, :external_link_taps,
        :engagement_rate, :bio_link_ctr
    )
    ON CONFLICT (account_id, snapshot_date)
    DO UPDATE SET
        followers           = EXCLUDED.followers,
        following           = EXCLUDED.following,
        total_posts         = EXCLUDED.total_posts,
        reach               = EXCLUDED.reach,
        views_total         = EXCLUDED.views_total,
        views_followers     = EXCLUDED.views_followers,
        views_non_followers = EXCLUDED.views_non_followers,
        views_reels         = EXCLUDED.views_reels,
        views_stories       = EXCLUDED.views_stories,
        views_posts         = EXCLUDED.views_posts,
        interactions_total  = EXCLUDED.interactions_total,
        interactions_reels  = EXCLUDED.interactions_reels,
        interactions_stories = EXCLUDED.interactions_stories,
        interactions_posts  = EXCLUDED.interactions_posts,
        accounts_engaged    = EXCLUDED.accounts_engaged,
        profile_visits      = EXCLUDED.profile_visits,
        external_link_taps  = EXCLUDED.external_link_taps,
        engagement_rate     = EXCLUDED.engagement_rate,
        bio_link_ctr        = EXCLUDED.bio_link_ctr
""")


# ──────────────────────────────────────────────────────────────
# account_active_hours — UPSERT on (account_id, snapshot_date, hour_of_day)
# ──────────────────────────────────────────────────────────────

_UPSERT_ACTIVE_HOUR = text("""
    INSERT INTO account_active_hours (
        account_id, snapshot_date, hour_of_day, online_count
    ) VALUES (
        :account_id, :snapshot_date, :hour_of_day, :online_count
    )
    ON CONFLICT (account_id, snapshot_date, hour_of_day)
    DO UPDATE SET
        online_count = EXCLUDED.online_count
""")


# ──────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────

def persist_account(transformed: dict) -> None:
    """
    Persist the output of ``transform_account_insights()`` to the database.

    Runs as a single transaction:
      1. UPSERT one row into ``account_daily``
      2. UPSERT 24 rows into ``account_active_hours``

    Parameters
    ----------
    transformed : dict
        ``{"account_daily": {…}, "account_active_hours": [{…}, …]}``
    """
    ensure_schema()

    conn = get_connection()
    try:
        # 1. account_daily — single row
        conn.execute(_UPSERT_ACCOUNT_DAILY, transformed["account_daily"])

        # 2. account_active_hours — one row per hour
        for hour_row in transformed["account_active_hours"]:
            conn.execute(_UPSERT_ACTIVE_HOUR, hour_row)

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
