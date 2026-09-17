from fastapi import APIRouter, HTTPException

from app.agent_service import run_agent
from app.models import AgentRequest, AgentResponse

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/chat", response_model=AgentResponse)
async def chat(request: AgentRequest):
    """Let the interview coach choose and run the right preparation tool."""
    try:
        return await run_agent(request.message, request.resume_text, request.job_description)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI Coach could not complete that request.") from exc