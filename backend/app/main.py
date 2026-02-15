from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers.conversations import router as conversations_router
from app.routers.lore import router as lore_router
from app.routers.messages import router as messages_router
from app.routers.settings import router as settings_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


app = FastAPI(title='Azimuth', lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(conversations_router)
app.include_router(messages_router)
app.include_router(settings_router)
app.include_router(lore_router)


@app.get('/api/health')
async def health() -> dict[str, str]:
    return {'status': 'ok'}
