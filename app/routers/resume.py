from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from app.models import ScenarioRequest, ScenarioSet
from app.llm_service import call_structured, build_scenario_prompt
from app.resume_parser import extract_resume_text
from app.services.resume_service import resolve_resume_text

router = APIRouter(prefix="/api/resume", tags=["resume-scenarios"])


@router.post("/extract-text")
async def extract_text(file: UploadFile = File(...)):
    """Utility endpoint: upload a resume, get back raw extracted text (used by the UI)."""
    text = await extract_resume_text(file)
    return {"filename": file.filename, "text": text}


@router.post("/scenarios", response_model=ScenarioSet)
async def scenarios_from_upload(
    file: Optional[UploadFile] = File(default=None),
    resume_text: Optional[str] = Form(default=None),
    role: Optional[str] = Form(default=None),
    job_description: Optional[str] = Form(default=None),
    num_scenarios: int = Form(default=6),
):
    """
    Generate scenario-based ('tell me about a time...') interview questions
    grounded in the candidate's actual resume. Accepts either a file upload
    or raw pasted resume_text.
    """
    text = await resolve_resume_text(file, resume_text)

    req = ScenarioRequest(
        resume_text=text,
        role=role,
        job_description=job_description,
        num_scenarios=num_scenarios,
    )
    system, user = build_scenario_prompt(req)
    try:
        return await call_structured(system, user, ScenarioSet)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI service could not build scenarios.") from exc
