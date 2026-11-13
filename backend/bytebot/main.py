from contextlib import asynccontextmanager
from fastapi import FastAPI
from .db import make_pool
from .settings import DATABASE_URL, GEMINI_API_KEY, GEMINI_MODEL, EXTRACTION_MODE
from .extraction import GeminiProvider
from .analysis_worker import AnalysisWorker
from .analysis_routes import router as analysis_router
from .incident_routes import router as incident_router
from .errors import install_errors, error
from .transactions import router
from .investigations import router as investigation_router
from .ocr import OCRAdapter
from .demo import router as demo_router


def create_app(database_url=DATABASE_URL, ocr_adapter=None, extraction_provider=None, worker_enabled=True):
    @asynccontextmanager
    async def lifespan(app):
        pool = make_pool(database_url)
        pool.open()
        app.state.pool = pool
        app.state.ocr = ocr_adapter or OCRAdapter()
        if extraction_provider is not None:
            app.state.extractor = extraction_provider
        elif EXTRACTION_MODE == 'fixture':
            from .fixtures import FixtureProvider
            app.state.extractor = FixtureProvider()
        elif EXTRACTION_MODE == 'gemini':
            app.state.extractor = GeminiProvider(GEMINI_API_KEY, GEMINI_MODEL)
        else:
            pool.close()
            raise RuntimeError('Unknown extraction mode')
        worker = AnalysisWorker(pool, app.state.extractor)
        if worker_enabled:
            worker.start()
        try:
            yield
        finally:
            await worker.close()
            pool.close()

    app = FastAPI(title="Byte Bot", lifespan=lifespan)
    install_errors(app)
    app.include_router(router, prefix="/api/v1")
    app.include_router(investigation_router, prefix="/api/v1")
    app.include_router(analysis_router, prefix="/api/v1")
    app.include_router(incident_router, prefix="/api/v1")
    app.include_router(demo_router, prefix="/api/v1")

    @app.middleware("http")
    async def private_responses(request, call_next):
        try:
            response = await call_next(request)
        except Exception:
            response = error(500, "internal_error", "The request could not be completed.")
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/v1/health")
    def health():
        try:
            with app.state.pool.connection() as conn:
                conn.execute("SELECT 1")
        except Exception:
            return error(503, "database_unavailable", "The database is temporarily unavailable.")
        return {"status": "ready", "database": "available"}

    return app


app = create_app()
