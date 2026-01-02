from fastapi import FastAPI
from .api.context import router

app = FastAPI(title="Profile Agent")

app.include_router(router)
