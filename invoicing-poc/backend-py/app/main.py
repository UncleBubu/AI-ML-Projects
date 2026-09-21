import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.jobs.scheduler import start_scheduler, stop_scheduler
from app.routers import ai as ai_router, customer_reminders, customers, expenses, invoices, reminders, reports, webhooks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Invoicing PoC", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.frontend_origins, allow_methods=["*"], allow_headers=["*"])


# The React app reads `body.error`, so present every failure in that shape.
@app.exception_handler(RequestValidationError)
async def validation_handler(_req: Request, exc: RequestValidationError):
    err = exc.errors()[0]
    field = ".".join(str(p) for p in err["loc"] if p != "body")
    return JSONResponse({"error": f"{field or 'body'}: {err['msg']}"}, status_code=400)


@app.exception_handler(HTTPException)
async def http_handler(_req: Request, exc: HTTPException):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


@app.exception_handler(Exception)
async def unhandled(_req: Request, exc: Exception):
    logging.getLogger("app").exception("Unhandled error")
    return JSONResponse({"error": "Internal server error"}, status_code=500)


@app.get("/health")
def health():
    return {"status": "ok"}


for r in (webhooks, customers, invoices, customer_reminders, expenses, reports, reminders, ai_router):
    app.include_router(r.router)
