from fastapi import FastAPI

from jobsift.api.health import router as health_router


def create_app() -> FastAPI:
    application = FastAPI(
        title="JobSift API",
        version="0.1.0",
        description="Public job aggregation and search API",
    )
    application.include_router(health_router, prefix="/api/v1")
    return application


app = create_app()
