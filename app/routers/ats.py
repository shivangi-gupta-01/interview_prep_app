import re
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


def _keywords(text: str) -> set[str]:
    return {word.lower() for word in re.findall(r"[a-zA-Z][a-zA-Z+#.-]{1,}", text)}


def _local_ats_report(resume_text: str, job_description: str | None) -> ATSReport:
    resume_words = _keywords(resume_text)
    jd_words = _keywords(job_description or "")
    target_words = {word for word in jd_words if len(word) > 2}
    matched = sorted(resume_words & target_words)
    missing = sorted(target_words - resume_words)
    section_names = {line.strip().lower() for line in resume_text.splitlines() if line.strip()}
    expected_sections = {"summary", "experience", "skills", "education", "projects"}
    section_score = min(100, 35 + 13 * len(expected_sections & section_names))
    quantified = sum(1 for line in resume_text.splitlines() if any(char.isdigit() for char in line))
    impact_score = min(100, 45 + quantified * 10)
    keyword_score = 72 if not target_words else min(100, round(len(matched) / max(len(target_words), 1) * 100))
    parse_score = 85 if len(resume_text.splitlines()) > 5 else 60
    clarity_score = 75 if len(resume_text) <= 12000 else 55
    overall = round(parse_score * .2 + keyword_score * .3 + section_score * .15 + impact_score * .2 + clarity_score * .15)
    return ATSReport(
        overall_score=overall,
        verdict="Good foundation with targeted improvements available.",
        category_scores=[
            {"name": "Parseability & Formatting", "score": parse_score, "max_score": 100, "findings": ["Use standard section headings and simple text formatting."]},
            {"name": "Keyword & Skills Match", "score": keyword_score, "max_score": 100, "findings": [f"Matched {len(matched)} target keywords."]},
            {"name": "Section Completeness", "score": section_score, "max_score": 100, "findings": [f"Recognized {len(expected_sections & section_names)} of {len(expected_sections)} common sections."]},
            {"name": "Impact & Quantification", "score": impact_score, "max_score": 100, "findings": ["Add measurable outcomes to more experience bullets."]},
            {"name": "Clarity & Length", "score": clarity_score, "max_score": 100, "findings": ["Keep bullets concise and focused on outcomes."]},
        ],
        missing_keywords=missing[:30],
        matched_keywords=matched[:30],
        quick_wins=["Add missing job keywords where they truthfully describe your experience.", "Rewrite duty-based bullets with action and measurable outcomes.", "Use standard headings: Summary, Experience, Skills, and Education."],
        formatting_issues=[],
    )


def _local_ats_optimize(resume_text: str, report: ATSReport | None) -> ATSOptimizeResult:
    rewritten = "\n".join(line.strip() for line in resume_text.splitlines() if line.strip())
    reason = "Preserved the original claims and normalized the resume into ATS-safe plain text."
    return ATSOptimizeResult(
        rewritten_sections=[{"section": "Full resume", "original": resume_text, "rewritten": rewritten, "reason": reason}],
        full_rewritten_resume=rewritten,
        projected_score=min(100, (report.overall_score if report else 60) + 12),
    )


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
        if "429" in str(exc) or "quota" in str(exc).lower() or "resourceexhausted" in str(exc).lower():
            return _local_ats_report(text, job_description)
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
        if "429" in str(exc) or "quota" in str(exc).lower() or "resourceexhausted" in str(exc).lower():
            return _local_ats_optimize(text, report)
        raise HTTPException(status_code=502, detail="AI service could not rewrite the resume.") from exc
