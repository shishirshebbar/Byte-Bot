from contextlib import asynccontextmanager
from fastapi import FastAPI
from .db import make_pool
from .settings import DATABASE_URL, GEMINI_API_KEY, GEMINI_MODEL, EXTRACTION_MODE, SARVAM_API_KEY, SARVAM_CHAT_MODEL
from .extraction import GeminiProvider
from .analysis_worker import AnalysisWorker
from .analysis_routes import router as analysis_router
from .incident_routes import router as incident_router
from .errors import install_errors, error
from .transactions import router
from .investigations import router as investigation_router
from .ocr import OCRAdapter
from .demo import router as demo_router
from .security import RateLimiter, DEFAULT_LIMITS, SECURITY_HEADERS
from .agent_routes import router as agent_router
from .console import router as console_router
from .voice_routes import router as voice_router
from .metrics import router as metrics_router


def create_app(database_url=DATABASE_URL, ocr_adapter=None, extraction_provider=None, worker_enabled=True, systems=None, speech=None,
               rate_limits=None):
    @asynccontextmanager
    async def lifespan(app):
        pool = make_pool(database_url)
        pool.open()
        app.state.pool = pool
        app.state.ocr = ocr_adapter or OCRAdapter()
        from .sarvam import SarvamClient
        app.state.speech = speech or SarvamClient(SARVAM_API_KEY)
        if extraction_provider is not None:
            app.state.extractor = extraction_provider
        elif EXTRACTION_MODE == 'fixture':
            from .fixtures import FixtureProvider
            app.state.extractor = FixtureProvider()
        elif EXTRACTION_MODE == 'sarvam':
            from .sarvam import SarvamProvider
            app.state.extractor = SarvamProvider(SARVAM_API_KEY, SARVAM_CHAT_MODEL)
        elif EXTRACTION_MODE == 'gemini':
            app.state.extractor = GeminiProvider(GEMINI_API_KEY, GEMINI_MODEL)
        else:
            pool.close()
            raise RuntimeError('Unknown extraction mode')
        from .systems import SimulatedSystems
        app.state.systems = systems or SimulatedSystems()
        worker = AnalysisWorker(pool, app.state.extractor, systems=app.state.systems)
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
    app.include_router(agent_router, prefix="/api/v1")
    app.include_router(console_router, prefix="/api/v1")
    app.include_router(voice_router, prefix="/api/v1")
    app.include_router(metrics_router, prefix="/api/v1")

    limiter = RateLimiter(rate_limits or DEFAULT_LIMITS)

    @app.middleware("http")
    async def private_responses(request, call_next):
        blocked = limiter.check(request)
        if blocked:
            response = error(429, "rate_limited", "Too many requests. Wait a moment and try again.")
            response.headers["Retry-After"] = str(blocked)
        else:
            try:
                response = await call_next(request)
            except Exception:
                response = error(500, "internal_error", "The request could not be completed.")
        response.headers["Cache-Control"] = "no-store"
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
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
