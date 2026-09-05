import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
import httpx
from .db import Base, engine, SessionLocal, settings
from .seed import seed
from .organizations import router as organization_router
from .prds import router as prd_router
from .llm import ProviderResponseError

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logging.getLogger('httpx').setLevel(logging.WARNING)
logger = logging.getLogger('copilot')


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db, settings.seed_demo)
    logger.info('Copilot ready; provider mode=%s', settings.llm_provider if settings.llm_api_key else 'mock')
    yield


app = FastAPI(title='Context — Product Copilot', version='0.1.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(','), allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'], allow_headers=['Content-Type'])
app.include_router(organization_router)
app.include_router(prd_router)


@app.exception_handler(ValidationError)
@app.exception_handler(ProviderResponseError)
async def invalid_ai_output(request: Request, exc: ValidationError):
    logger.warning('Structured output validation failed')
    return JSONResponse(status_code=502, content={'detail': 'The AI returned an invalid response. Nothing was saved. Please retry.'})


@app.exception_handler(httpx.HTTPError)
async def provider_error(request: Request, exc: httpx.HTTPError):
    logger.warning('AI provider request failed: %s', type(exc).__name__)
    return JSONResponse(status_code=502, content={'detail': 'The AI provider is unavailable. Your work is preserved. Please retry.'})


@app.get('/health')
def health():
    return {'status': 'ok', 'provider': settings.llm_provider if settings.llm_api_key else 'mock', 'workspace_mode': 'demo'}
