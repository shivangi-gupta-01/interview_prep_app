from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from app.models import (
    ATSScoreRequest,
    ATSReport,
    ATSOptimizeRequest,
    ATSOptimizeResult,
)
from app.llm_service import call_structured, build_ats_score_prompt, build_ats_optimize_prompt
from app.services.resume_service import resolve_resume_text

router = APIRouter(prefix="/api/ats", tags=["ats"])


@router.post("/score", response_model=ATSReport)
async def score_resume(
    file: Optional[UploadFile] = File(default=None),
    resume_text: Optional[str] = Form(default=None),
    job_description: Optional[str] = Form(default=None),
):
    """
    Score a resume's ATS-friendliness (0-100) with a per-category breakdown,
    keyword match against a job description (if provided), and quick wins.
    """
    text = await resolve_resume_text(file, resume_text)
    req = ATSScoreRequest(resume_text=text, job_description=job_description)
    system, user = build_ats_score_prompt(req)
    try:
        return await call_structured(system, user, ATSReport)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI service could not score the resume.") from exc


@router.post("/optimize", response_model=ATSOptimizeResult)
async def optimize_resume(
    file: Optional[UploadFile] = File(default=None),
    resume_text: Optional[str] = Form(default=None),
    job_description: Optional[str] = Form(default=None),
    ats_report: Optional[str] = Form(default=None),
):
    """
    Rewrite the resume section-by-section to push ATS-friendliness toward 100%,
    plus return a full rewritten resume as plain text.
    """
    text = await resolve_resume_text(file, resume_text)
    report = None
    if ats_report:
        try:
            report = ATSReport.model_validate_json(ats_report)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="The ATS report is invalid. Please score the resume again.") from exc
    req = ATSOptimizeRequest(resume_text=text, job_description=job_description, ats_report=report)
    system, user = build_ats_optimize_prompt(req)
    try:
        return await call_structured(system, user, ATSOptimizeResult)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI service could not rewrite the resume.") from exc
