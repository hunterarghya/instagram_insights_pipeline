from sqlalchemy import MetaData, inspect
from db.database import get_engine
from config.settings import get_settings


def get_metadata() -> MetaData:
    """Reflect all tables from the configured schema."""
    settings = get_settings()
    engine = get_engine()
    metadata = MetaData(schema=settings.db.schema)
    metadata.reflect(bind=engine)
    return metadata


def get_all_tables() -> list[str]:
    """Return list of all table names in the configured schema."""
    settings = get_settings()
    engine = get_engine()
    inspector = inspect(engine)
    return inspector.get_table_names(schema=settings.db.schema)


def get_table_columns(table_name: str) -> list[dict]:
    """Return column details for a specific table."""
    settings = get_settings()
    engine = get_engine()
    inspector = inspect(engine)
    return inspector.get_columns(table_name, schema=settings.db.schema)
