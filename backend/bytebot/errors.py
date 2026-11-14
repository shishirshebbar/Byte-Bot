import logging
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
import psycopg
from psycopg_pool import PoolTimeout
from .ocr import EvidenceError

logger = logging.getLogger(__name__)


def error(status, code, message):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def install_errors(app):
    @app.exception_handler(EvidenceError)
    async def evidence_error(request: Request, exc):
        return error(exc.status, exc.code, exc.message)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc):
        if exc.status_code == 404:
            return error(404, "not_found", "Transaction not found.")
        return error(exc.status_code, "request_failed", "The request could not be completed.")

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc):
        return error(422, "invalid_input", "Check the supplied field values.")

    @app.exception_handler(psycopg.OperationalError)
    @app.exception_handler(PoolTimeout)
    async def database_error(request: Request, exc):
        return error(503, "database_unavailable", "The database is temporarily unavailable.")

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc):
        logger.error(f"Unexpected error in {request.method} {request.url.path}: {type(exc).__name__}: {exc}", exc_info=exc)
        return error(500, "request_failed", "The request could not be completed.")
