"""
Repository: collaborators + post_collaborators.

All functions accept the row dicts produced by transform/collaborator.py
and persist them using raw SQL via SQLAlchemy text().

Write patterns:
    - collaborators:      UPSERT on (collaborator_id)
    - post_collaborators: INSERT … ON CONFLICT DO NOTHING
"""

from sqlalchemy import text
from db.database import get_connection
from repository.schema import ensure_schema


# ──────────────────────────────────────────────────────────────
# collaborators — UPSERT on (collaborator_id)
# ──────────────────────────────────────────────────────────────

_UPSERT_COLLABORATOR = text("""
    INSERT INTO collaborators (
        collaborator_id, username, followers_count, invite_status
    ) VALUES (
        :collaborator_id, :username, :followers_count, :invite_status
    )
    ON CONFLICT (collaborator_id)
    DO UPDATE SET
        username        = EXCLUDED.username,
        followers_count = EXCLUDED.followers_count,
        invite_status   = EXCLUDED.invite_status,
        last_updated_at = now()
""")


# ──────────────────────────────────────────────────────────────
# post_collaborators — INSERT IGNORE on (post_id, collaborator_id)
# ──────────────────────────────────────────────────────────────

_INSERT_POST_COLLABORATOR = text("""
    INSERT INTO post_collaborators (
        post_id, collaborator_id
    ) VALUES (
        :post_id, :collaborator_id
    )
    ON CONFLICT (post_id, collaborator_id)
    DO NOTHING
""")


# ──────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────

def persist_collaborators(transformed: dict) -> None:
    """
    Persist the output of ``transform_collaborators()`` to the database.

    Runs as a single transaction:
      1. UPSERT rows into ``collaborators``
      2. INSERT link rows into ``post_collaborators`` (skip duplicates)

    Parameters
    ----------
    transformed : dict
        ``{"collaborators": [{...}], "post_collaborators": [{...}]}``
    """
    ensure_schema()

    conn = get_connection()
    try:
        # 1. collaborators (must go first — post_collaborators references collaborator_id)
        for row in transformed["collaborators"]:
            conn.execute(_UPSERT_COLLABORATOR, row)

        # 2. post_collaborators link rows
        for row in transformed["post_collaborators"]:
            conn.execute(_INSERT_POST_COLLABORATOR, row)

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
