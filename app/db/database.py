import sys
from sqlalchemy import create_engine, text
from config.settings import get_settings


_engine = None


def get_engine():
    """Get or create a singleton SQLAlchemy engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.db.connection_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
    return _engine


def get_connection():
    """
    Get a raw SQLAlchemy connection with the search_path set to the configured schema.
    """
    engine = get_engine()
    conn = engine.connect()
    schema = get_settings().db.schema
    conn.execute(text(f"SET search_path TO {schema}, public"))
    return conn


def test_connection() -> bool:
    """Test database connectivity. Returns True on success."""
    
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        return True

    except Exception as e:
        print(f"[ERROR] Database connection failed: {e}", file=sys.stderr)
        return False
