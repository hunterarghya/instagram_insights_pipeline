"""
Schema initialisation — CREATE TABLE IF NOT EXISTS for all tables.

Called once at startup or before the first write.  Every statement
is idempotent so it is safe to run repeatedly.
"""

from sqlalchemy import text
from db.database import get_engine
from config.settings import get_settings


_DDL = """
-- Ensure the schema exists
CREATE SCHEMA IF NOT EXISTS {schema};
SET search_path TO {schema}, public;

-- =========================================================
-- 1. ACCOUNT-LEVEL DAILY SNAPSHOT
-- =========================================================
CREATE TABLE IF NOT EXISTS account_daily (
    snapshot_id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id             BIGINT      NOT NULL,
    snapshot_date          DATE        NOT NULL,

    followers              INTEGER,
    following              INTEGER,
    total_posts            INTEGER,
    reach                  INTEGER,

    views_total            INTEGER,
    views_followers        INTEGER,
    views_non_followers    INTEGER,
    views_reels            INTEGER,
    views_stories          INTEGER,
    views_posts            INTEGER,

    interactions_total         INTEGER,
    interactions_reels         INTEGER,
    interactions_stories       INTEGER,
    interactions_posts         INTEGER,

    accounts_engaged       INTEGER,
    profile_visits         INTEGER,
    external_link_taps     INTEGER,

    engagement_rate        NUMERIC(6,4),
    bio_link_ctr           NUMERIC(6,4),

    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (account_id, snapshot_date)
);

-- =========================================================
-- 2. MOST ACTIVE TIMES
-- =========================================================
CREATE TABLE IF NOT EXISTS account_active_hours (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id     BIGINT   NOT NULL,
    snapshot_date  DATE     NOT NULL,
    hour_of_day    SMALLINT NOT NULL,
    online_count   INTEGER,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (account_id, snapshot_date, hour_of_day)
);

-- =========================================================
-- 3. POSTS (current state, UPSERT)
-- =========================================================
CREATE TABLE IF NOT EXISTS posts (
    post_id            BIGINT PRIMARY KEY,
    account_id         BIGINT NOT NULL,
    media_type         TEXT,
    sub_brand_tag      TEXT,
    caption            TEXT,
    hashtags           TEXT[],
    posted_at          TIMESTAMPTZ,

    views              INTEGER,
    reach              INTEGER,
    likes              INTEGER,
    comments           INTEGER,
    shares             INTEGER,
    saves              INTEGER,
    interactions_total INTEGER,
    profile_visits     INTEGER,

    last_updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================================================
-- 4. POST DAILY SNAPSHOT (APPEND / UPSERT per day)
-- =========================================================
CREATE TABLE IF NOT EXISTS post_daily (
    snapshot_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    post_id            BIGINT NOT NULL REFERENCES posts(post_id),
    snapshot_date      DATE   NOT NULL,

    views              INTEGER,
    reach              INTEGER,
    likes              INTEGER,
    comments           INTEGER,
    shares             INTEGER,
    saves              INTEGER,
    interactions_total INTEGER,
    profile_visits     INTEGER,

    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (post_id, snapshot_date)
);

-- =========================================================
-- 5. POST REACH / ACTION BREAKDOWN
-- =========================================================
CREATE TABLE IF NOT EXISTS post_reach_breakdown (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    post_id        BIGINT NOT NULL REFERENCES posts(post_id),
    snapshot_date  DATE   NOT NULL,
    action_type    TEXT   NOT NULL,
    value          INTEGER,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (post_id, snapshot_date, action_type)
);

-- =========================================================
-- 6. COLLABORATORS
-- =========================================================
CREATE TABLE IF NOT EXISTS collaborators (
    collaborator_id  BIGINT PRIMARY KEY,
    username         TEXT,
    followers_count  INTEGER,
    invite_status    TEXT,
    last_updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================================================
-- 7. POST <-> COLLABORATOR link
-- =========================================================
CREATE TABLE IF NOT EXISTS post_collaborators (
    post_id          BIGINT NOT NULL REFERENCES posts(post_id),
    collaborator_id  BIGINT NOT NULL REFERENCES collaborators(collaborator_id),
    PRIMARY KEY (post_id, collaborator_id)
);

-- =========================================================
-- Indexes (IF NOT EXISTS is implicit for CREATE INDEX)
-- =========================================================
CREATE INDEX IF NOT EXISTS idx_account_daily_date  ON account_daily (snapshot_date);
CREATE INDEX IF NOT EXISTS idx_post_daily_date     ON post_daily (snapshot_date);
CREATE INDEX IF NOT EXISTS idx_posts_account       ON posts (account_id);
CREATE INDEX IF NOT EXISTS idx_active_hours_date   ON account_active_hours (snapshot_date, hour_of_day);
"""


_initialised = False


def ensure_schema():
    """
    Create the schema and all tables if they do not already exist.
    Safe to call multiple times — only runs DDL on the first call.
    """
    global _initialised
    if _initialised:
        return

    schema = get_settings().db.schema
    ddl = _DDL.format(schema=schema)

    engine = get_engine()
    with engine.connect() as conn:
        # Execute statements one at a time (some drivers don't support
        # multi-statement execution).
        for statement in ddl.split(";"):
            stmt = statement.strip()
            if stmt:
                conn.execute(text(stmt))
        conn.commit()

    _initialised = True
