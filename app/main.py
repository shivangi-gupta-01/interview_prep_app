"""
AI Interview Coach — FastAPI application entrypoint.

Run locally:
    uvicorn app.main:app --reload --port 8000

Then open http://localhost:8000
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.routers import agent, interview, resume, ats

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "1) Role/JD-based interview question generation  "
        "2) Resume-grounded scenario-based prep  "
        "3) ATS resume scoring & optimization"
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(interview.router)
app.include_router(resume.router)
app.include_router(ats.router)
app.include_router(agent.router)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "app_name": settings.app_name})


@app.get("/api/health")
def health():
    return {"status": "ok", "model": settings.gemini_model}
