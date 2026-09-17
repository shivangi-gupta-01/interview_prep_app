"""
Pydantic schemas shared across routers.
"""
from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 1) General / role-based interview prep
# ---------------------------------------------------------------------------
class InterviewRequest(BaseModel):
    role: str = Field(..., examples=["Backend Engineer"])
    skills: list[str] = Field(default_factory=list, examples=[["Python", "Django", "PostgreSQL"]])
    job_description: Optional[str] = Field(
        default=None, description="Paste the JD for a fully tailored session"
    )
    experience_level: str = Field(
        default="mid", description="entry | mid | senior | lead"
    )
    question_mix: str = Field(
        default="balanced",
        description="balanced | technical | behavioral | system_design",
    )
    num_questions: int = Field(default=8, ge=1, le=20)
    company: Optional[str] = Field(default=None, description="Target company, if known")


class InterviewQuestion(BaseModel):
    id: int
    category: str  # technical | behavioral | system_design | situational
    difficulty: str  # easy | medium | hard
    question: str = Field(max_length=500)
    why_asked: str = Field(max_length=300)
    what_good_answer_covers: list[str] = Field(max_length=5)
    follow_ups: list[str] = Field(default_factory=list, max_length=3)


class InterviewSet(BaseModel):
    role: str
    focus_summary: str = Field(max_length=400)
    questions: list[InterviewQuestion] = Field(max_length=20)


class AnswerEvaluationRequest(BaseModel):
    question: str
    answer: str
    role: Optional[str] = None
    category: Optional[str] = None


class AnswerEvaluation(BaseModel):
    score: int  # 0-100
    strengths: list[str] = Field(max_length=4)
    gaps: list[str] = Field(max_length=4)
    improved_answer: str = Field(max_length=1200)
    star_check: Optional[str] = Field(default=None, max_length=300)


# ---------------------------------------------------------------------------
# 2) Resume-based scenario prep
# ---------------------------------------------------------------------------
class ScenarioRequest(BaseModel):
    resume_text: str
    role: Optional[str] = None
    job_description: Optional[str] = None
    num_scenarios: int = Field(default=6, ge=1, le=15)


class Scenario(BaseModel):
    id: int
    based_on: str  # which resume line/project this draws from
    scenario_question: str
    hints: list[str]
    ideal_structure: list[str]  # STAR beats tailored to this scenario


class ScenarioSet(BaseModel):
    resume_highlights: list[str] = Field(max_length=8)
    scenarios: list[Scenario] = Field(max_length=15)


# ---------------------------------------------------------------------------
# 3) ATS resume scoring / optimization
# ---------------------------------------------------------------------------
class ATSScoreRequest(BaseModel):
    resume_text: str
    job_description: Optional[str] = None


class ATSCategoryScore(BaseModel):
    name: str
    score: int  # 0-100
    max_score: int
    findings: list[str]


class ATSReport(BaseModel):
    overall_score: int  # 0-100
    verdict: str
    category_scores: list[ATSCategoryScore]
    missing_keywords: list[str]
    matched_keywords: list[str]
    quick_wins: list[str]
    formatting_issues: list[str]


class ATSOptimizeRequest(BaseModel):
    resume_text: str
    job_description: Optional[str] = None
    ats_report: Optional[ATSReport] = None


class AgentRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    resume_text: Optional[str] = Field(default=None, max_length=30000)
    job_description: Optional[str] = Field(default=None, max_length=20000)


class AgentResponse(BaseModel):
    answer: str = Field(max_length=4000)
    action: str
    data: Optional[dict] = None


class ResumeSection(BaseModel):
    section: str
    original: str
    rewritten: str
    reason: str


class ATSOptimizeResult(BaseModel):
    rewritten_sections: list[ResumeSection]
    full_rewritten_resume: str
    projected_score: int
