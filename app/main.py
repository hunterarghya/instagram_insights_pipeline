from fastapi import FastAPI
from api.routers.health import router as health_router
from api.routers.sync import router as sync_router

app = FastAPI()

app.include_router(health_router)
app.include_router(sync_router)