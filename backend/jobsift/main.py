from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from jobsift.api.health import router as health_router
from jobsift.api.search import router as search_router
from jobsift.config import get_settings
from jobsift.search.gateway import ElasticsearchGateway
from jobsift.search.service import JobSearchService

WEB_ROOT = Path(__file__).parent / "web"


def create_app() -> FastAPI:
    settings = get_settings()
    client = httpx.Client(
        base_url=str(settings.elasticsearch_url),
        timeout=settings.elasticsearch_timeout_seconds,
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        yield
        client.close()

    application = FastAPI(
        title="JobSift API",
        version="0.1.0",
        description="Public job aggregation and search API",
        lifespan=lifespan,
    )
    application.state.search_service = JobSearchService(
        ElasticsearchGateway(client), alias=settings.elasticsearch_alias
    )
    application.include_router(health_router, prefix="/api/v1")
    application.include_router(search_router, prefix="/api/v1")
    application.mount("/assets", StaticFiles(directory=WEB_ROOT), name="assets")

    @application.get("/", include_in_schema=False)
    def web_client() -> FileResponse:
        return FileResponse(WEB_ROOT / "index.html")

    return application


app = create_app()
