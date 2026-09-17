"""Tool-using LangChain agent for natural-language interview coaching."""

import json

from langchain.agents import create_agent
from langchain.tools import tool

from app.llm_service import (
    build_ats_optimize_prompt,
    build_ats_score_prompt,
    build_interview_prompt,
    build_scenario_prompt,
    call_structured,
    get_llm,
)
from app.models import (
    ATSOptimizeRequest,
    ATSOptimizeResult,
    ATSReport,
    AgentResponse,
    AnswerEvaluation,
    InterviewRequest,
    InterviewSet,
    ScenarioRequest,
    ScenarioSet,
)


def _json(value) -> str:
    return value.model_dump_json()


@tool
async def generate_interview_questions(request_json: str) -> str:
    """Generate interview questions. Input JSON must contain role and may contain skills, level, and job description."""
    request = InterviewRequest.model_validate_json(request_json)
    system, user = build_interview_prompt(request)
    return _json(await call_structured(system, user, InterviewSet))


@tool
async def create_resume_scenarios(request_json: str) -> str:
    """Create STAR-based interview scenarios from resume text. Input JSON must contain resume_text."""
    request = ScenarioRequest.model_validate_json(request_json)
    system, user = build_scenario_prompt(request)
    return _json(await call_structured(system, user, ScenarioSet))


@tool
async def score_resume(request_json: str) -> str:
    """Score a resume for ATS readiness. Input JSON must contain resume_text and may contain job_description."""
    request = ATSOptimizeRequest.model_validate_json(request_json)
    score_request = request.model_copy(update={"ats_report": None})
    system, user = build_ats_score_prompt(score_request)
    return _json(await call_structured(system, user, ATSReport))


@tool
async def optimize_resume(request_json: str) -> str:
    """Rewrite a resume for ATS. Input JSON must contain resume_text and may include job_description and ats_report."""
    request = ATSOptimizeRequest.model_validate_json(request_json)
    system, user = build_ats_optimize_prompt(request)
    return _json(await call_structured(system, user, ATSOptimizeResult))


AGENT_PROMPT = """You are Interview Coach, a concise resume and interview preparation agent.
Decide which tool best answers the user's request. Use the supplied resume and job description
context when a tool needs them. Never invent resume experience. Keep the final answer under
400 words and summarize the tool result clearly. Return the requested structured response."""


async def run_agent(message: str, resume_text: str | None = None, job_description: str | None = None) -> AgentResponse:
    context = {
        "user_request": message,
        "resume_text": resume_text,
        "job_description": job_description,
    }
    agent = create_agent(
        model=get_llm(),
        tools=[generate_interview_questions, create_resume_scenarios, score_resume, optimize_resume],
        system_prompt=AGENT_PROMPT,
        response_format=AgentResponse,
    )
    result = await agent.ainvoke({"messages": [{"role": "user", "content": json.dumps(context)}]})
    response = result.get("structured_response")
    if isinstance(response, AgentResponse):
        return response
    return AgentResponse(answer="The agent could not produce a structured response.", action="none")