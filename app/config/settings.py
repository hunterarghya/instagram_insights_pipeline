import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class DBSettings:
    host: str
    port: int
    name: str
    user: str
    password: str
    schema: str

    @property
    def connection_url(self) -> str:
        """PostgreSQL connection URL for psycopg2."""
        from urllib.parse import quote_plus
        pwd = quote_plus(self.password)
        ssl = os.getenv(
            "DB_SSLMODE",
            "disable" if self.host in ("localhost", "127.0.0.1", "::1", "postgres", "db") else "require",
        )
        return (
            f"postgresql+psycopg2://{self.user}:{pwd}"
            f"@{self.host}:{self.port}/{self.name}?sslmode={ssl}"
        )

    @property
    def dsn(self) -> str:
        """Plain DSN string for psycopg2.connect()."""
        ssl = os.getenv(
            "DB_SSLMODE",
            "disable" if self.host in ("localhost", "127.0.0.1", "::1", "postgres", "db") else "require",
        )
        return (
            f"host={self.host} port={self.port} dbname={self.name} "
            f"user={self.user} password={self.password} sslmode={ssl}"
        )


@dataclass(frozen=True)
class InstagramSettings:
    account_id: str
    access_token: str
    api_version: str
    base_url: str

    @property
    def api_base(self) -> str:
        """Full base URL including version, e.g. https://graph.facebook.com/v25.0"""
        return f"{self.base_url}/{self.api_version}"


@dataclass(frozen=True)
class Settings:
    db: DBSettings
    instagram: InstagramSettings
    dummy_switch: bool


def get_settings() -> Settings:
    """Load and validate settings from environment variables."""
    required = {"DB_HOST", "DB_NAME", "DB_USER", "DB_PASS"}
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise ValueError(f"Missing required env vars: {', '.join(missing)}")

    db = DBSettings(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "5432")),
        name=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        schema=os.getenv("DB_SCHEMA", "public"),
    )

    instagram = InstagramSettings(
        account_id=os.getenv("IG_ACCOUNT_ID", ""),
        access_token=os.getenv("IG_ACCESS_TOKEN", ""),
        api_version=os.getenv("GRAPH_API_VERSION", "v25.0"),
        base_url=os.getenv("GRAPH_BASE_URL", "https://graph.facebook.com"),
    )

    dummy_switch = os.getenv("DUMMY_SWITCH", "0") == "1"

    return Settings(db=db, instagram=instagram, dummy_switch=dummy_switch)
