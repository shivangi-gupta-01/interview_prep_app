from fastapi import APIRouter, HTTPException

from app.models import (
    InterviewRequest,
    InterviewSet,
    AnswerEvaluationRequest,
    AnswerEvaluation,
)
from app.llm_service import call_structured, build_interview_prompt, build_answer_eval_prompt

router = APIRouter(prefix="/api/interview", tags=["interview"])


@router.post("/questions", response_model=InterviewSet)
async def generate_questions(req: InterviewRequest):
    """
    Generate a personalized interview question set for a role/skill set,
    optionally tailored to a specific job description.
    """
    system, user = build_interview_prompt(req)
    try:
        return await call_structured(system, user, InterviewSet)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI service could not generate questions.") from exc


@router.post("/evaluate", response_model=AnswerEvaluation)
async def evaluate_answer(req: AnswerEvaluationRequest):
    """
    Score a candidate's spoken/written answer and return an improved version.
    """
    system, user = build_answer_eval_prompt(req)
    try:
        return await call_structured(system, user, AnswerEvaluation)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI service could not evaluate that answer.") from exc
