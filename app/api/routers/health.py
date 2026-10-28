from fastapi import APIRouter
from db.database import test_connection

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    """
    Returns the overall service health and database connectivity status.
    """
    db_ok = test_connection()
    status = "healthy" if db_ok else "degraded"
    return {
        "status": status,
        "database": "connected" if db_ok else "unreachable",
    }
