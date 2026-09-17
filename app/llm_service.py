"""
Thin wrapper around the Google Gemini API (google-genai SDK).

Centralizes:
  - client construction
  - a "call and get JSON back" helper (with retries + repair pass)
  - all prompt templates for the three product features
"""
import asyncio
import hashlib
import time
from typing import TypeVar

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

from app.config import get_settings

settings = get_settings()
T = TypeVar("T", bound=BaseModel)
_response_cache: dict[str, tuple[float, BaseModel]] = {}
_inflight: dict[str, asyncio.Task] = {}
_CACHE_TTL_SECONDS = 300


def get_llm() -> ChatGoogleGenerativeAI:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set. Add it to your .env file.")
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=45,
        max_retries=0,
    )


async def call_structured(system_prompt: str, user_prompt: str, schema: type[T]) -> T:
    """Call Gemini once per identical request and require a complete typed result."""
    cache_key = hashlib.sha256(
        f"{schema.__name__}\0{system_prompt}\0{user_prompt}".encode("utf-8")
    ).hexdigest()
    cached = _response_cache.get(cache_key)
    if cached and time.monotonic() - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]  # type: ignore[return-value]
    _response_cache.pop(cache_key, None)

    task = _inflight.get(cache_key)
    if task is None:
        task = asyncio.create_task(_generate_structured(system_prompt, user_prompt, schema))
        _inflight[cache_key] = task
    try:
        result = await task
        _response_cache[cache_key] = (time.monotonic(), result)
        return result
    finally:
        if task.done() and _inflight.get(cache_key) is task:
            _inflight.pop(cache_key, None)


async def _generate_structured(system_prompt: str, user_prompt: str, schema: type[T]) -> T:
    structured_llm = get_llm().with_structured_output(schema, method="json_schema")
    last_error = None
    for attempt in range(2):
        try:
            result = await structured_llm.ainvoke([
                ("system", system_prompt),
                ("human", user_prompt),
            ])
            return result if isinstance(result, schema) else schema.model_validate(result)
        except Exception as exc:
            last_error = exc
            error_text = str(exc).lower()
            if attempt == 0 and "429" not in error_text and "quota" not in error_text and "resourceexhausted" not in error_text:
                await asyncio.sleep(0.25)
    raise last_error  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

JSON_ONLY_RULE = (
    "Respond with ONLY valid JSON matching the requested schema. "
    "No markdown fences, no preamble, no commentary outside the JSON object."
)


def build_interview_prompt(req) -> tuple[str, str]:
    system = (
        "You are a senior technical interviewer and career coach with deep "
        "expertise across backend engineering (Python, Django, Flask, FastAPI), "
        "MERN, databases (MySQL/PostgreSQL), Docker, AWS, and applied AI/LLM "
        "systems. You design realistic, role-calibrated interview questions "
        "and rubrics. Keep explanations short and practical. " + JSON_ONLY_RULE
    )
    jd_block = f"\nJob description:\n{req.job_description}\n" if req.job_description else ""
    company_block = f"Target company: {req.company}\n" if req.company else ""
    user = f"""
Generate a personalized interview question set.

Role: {req.role}
Experience level: {req.experience_level}
Key skills to probe: {", ".join(req.skills) if req.skills else "infer from role"}
Question mix requested: {req.question_mix}
Number of questions: {req.num_questions}
{company_block}{jd_block}
Rules:
- If a job description is provided, tailor questions tightly to its stated responsibilities and requirements.
- Mix technical depth questions, behavioral (STAR-style) questions, and — for mid/senior/lead — system design or architecture questions, in proportions matching "question_mix".
- Each question must include: category, difficulty, the question text, why an interviewer asks it, a bullet list of what a strong answer should cover, and 1-2 realistic follow-up questions.
- Make questions specific and non-generic (avoid "tell me about yourself" unless behavioral mix explicitly needs an opener).

Return JSON matching exactly this schema:
{{
  "role": "string",
  "focus_summary": "1-2 sentence summary of what this session emphasizes and why",
  "questions": [
    {{
      "id": 1,
      "category": "technical|behavioral|system_design|situational",
      "difficulty": "easy|medium|hard",
      "question": "string",
      "why_asked": "string",
      "what_good_answer_covers": ["string", "..."],
      "follow_ups": ["string", "..."]
    }}
  ]
}}
"""
    return system, user


def build_answer_eval_prompt(req) -> tuple[str, str]:
    system = (
        "You are a strict but constructive interview coach. You evaluate "
        "candidate answers the way a hiring committee would, and rewrite "
        "weak answers into strong, specific, metrics-backed ones. Be concise. " + JSON_ONLY_RULE
    )
    user = f"""
Question asked: {req.question}
Role context: {req.role or "not specified"}
Category: {req.category or "not specified"}

Candidate's answer:
\"\"\"{req.answer}\"\"\"

Evaluate this answer. If it is a behavioral/situational question, explicitly assess
STAR structure (Situation, Task, Action, Result) — note it in "star_check", or set
"star_check" to null if not applicable (e.g. pure technical Q&A).

Return JSON matching exactly this schema:
{{
  "score": 0,
  "strengths": ["string"],
  "gaps": ["string"],
  "improved_answer": "a rewritten, stronger version of the answer in first person, realistic length",
  "star_check": "string or null"
}}
"""
    return system, user


def build_scenario_prompt(req) -> tuple[str, str]:
    system = (
        "You are a career coach who converts a candidate's actual resume "
        "content into realistic scenario-based / situational interview "
        "questions ('Tell me about a time...', 'How would you handle...') "
        "grounded in their real projects and claims, so they can rehearse "
        "specific, credible stories instead of generic answers. Keep hints brief. " + JSON_ONLY_RULE
    )
    role_block = f"Target role: {req.role}\n" if req.role else ""
    jd_block = f"Job description:\n{req.job_description}\n" if req.job_description else ""
    user = f"""
Resume text (raw extracted text, formatting may be imperfect):
\"\"\"{req.resume_text}\"\"\"

{role_block}{jd_block}
Task:
1. Identify 4-8 concrete highlights from the resume (specific projects, technologies, achievements, metrics, leadership moments) worth building interview stories around.
2. Generate {req.num_scenarios} scenario-based interview questions, each explicitly tied to one resume highlight (reference it in "based_on"), plus realistic hypothetical extensions
   (e.g. "your resume mentions migrating a monolith to microservices — how would you handle a rollback if the migration broke production checkout?").
3. For each scenario give 2-4 hints (things to mention) and an ideal STAR-style structure tailored to that scenario (4 short bullet beats).
4. If a target role/JD is given, bias scenarios toward what that role would actually probe.

Return JSON matching exactly this schema:
{{
  "resume_highlights": ["string", "..."],
  "scenarios": [
    {{
      "id": 1,
      "based_on": "which resume item this draws from",
      "scenario_question": "string",
      "hints": ["string", "..."],
      "ideal_structure": ["Situation: ...", "Task: ...", "Action: ...", "Result: ..."]
    }}
  ]
}}
"""
    return system, user


def build_ats_score_prompt(req) -> tuple[str, str]:
    system = (
        "You are an ATS (Applicant Tracking System) resume auditor and "
        "technical recruiter with 10+ years screening resumes for software "
        "engineering roles. You know exactly how parsers extract sections, "
        "how keyword matching works, and what formatting breaks parsing. "
        "You give precise, numeric, defensible scores — not vague praise. Keep findings to one sentence. " + JSON_ONLY_RULE
    )
    jd_block = (
        f"\nTarget job description (score keyword match against this):\n{req.job_description}\n"
        if req.job_description
        else "\nNo job description was provided — score general ATS/parseability best practices and infer likely target keywords from the resume's own field.\n"
    )
    user = f"""
Resume text (raw extracted text):
\"\"\"{req.resume_text}\"\"\"
{jd_block}
Score this resume for ATS-friendliness across these categories (each out of 100, then combined into an overall weighted score out of 100):
1. "Parseability & Formatting" (weight 20) — standard section headers, no tables/columns/graphics/text-boxes that break parsers, consistent date formats, no headers/footers with critical info.
2. "Keyword & Skills Match" (weight 30) — presence of hard skills/tools/keywords from the JD (or role norms if no JD), natural placement (not stuffed).
3. "Section Completeness" (weight 15) — Contact info, Summary, Experience, Skills, Education, (Projects/Certifications if relevant) all present and correctly labeled.
4. "Impact & Quantification" (weight 20) — bullets use strong action verbs and quantify results (%, $, time saved, scale) rather than listing duties.
5. "Clarity & Length" (weight 15) — concise bullets, appropriate length (~1-2 pages equivalent), no fluff/buzzword soup, consistent tense.

For each category return a 0-100 score and 2-4 specific findings referencing actual resume content.
Also return: overall_score (0-100, weighted per above), a one-line verdict, missing_keywords (present in JD/role-norms but absent from resume), matched_keywords (present in both), quick_wins (3-6 highest-leverage fixes ranked by impact), and formatting_issues (concrete parsing risks found, empty list if none).

Return JSON matching exactly this schema:
{{
  "overall_score": 0,
  "verdict": "string",
  "category_scores": [
    {{"name": "string", "score": 0, "max_score": 100, "findings": ["string"]}}
  ],
  "missing_keywords": ["string"],
  "matched_keywords": ["string"],
  "quick_wins": ["string"],
  "formatting_issues": ["string"]
}}
"""
    return system, user


def build_ats_optimize_prompt(req) -> tuple[str, str]:
    system = (
        "You are an expert resume writer specializing in ATS optimization "
        "for software engineering roles. You rewrite resume content to "
        "maximize both machine parseability and human impact — strong verbs, "
        "quantified results, relevant keywords worked in naturally — without "
        "fabricating experience the candidate didn't have. Keep reasons and bullets compact. " + JSON_ONLY_RULE
    )
    jd_block = f"\nTarget job description:\n{req.job_description}\n" if req.job_description else ""
    prior = ""
    if req.ats_report:
        prior = f"\nPrior ATS audit findings to address:\n{req.ats_report.model_dump_json(indent=2)}\n"
    user = f"""
Original resume text:
\"\"\"{req.resume_text}\"\"\"
{jd_block}{prior}
Task:
1. Rewrite the resume section by section (Summary, Skills, each Experience entry, Projects, Education as applicable) to be maximally ATS-friendly and impactful.
   - Use standard section names.
   - Rewrite weak/duty-based bullets into strong action-verb + task + quantified-result bullets. Only quantify with numbers reasonably implied by the original text — do not invent fake metrics; if no number is inferable, strengthen the verb/impact language instead and flag it needs a real number.
   - Naturally weave in missing keywords from the JD where truthfully applicable.
   - Fix formatting/parseability issues (plain section headers, consistent dates, no special characters that break parsers).
2. For each rewritten section, briefly state the reason for the change.
3. Assemble a full rewritten resume as plain text (ATS-safe formatting: no tables, no columns, standard headers, consistent bullet style using "- ").
4. Give a projected_score (0-100) estimating ATS-friendliness after these changes.

Return JSON matching exactly this schema:
{{
  "rewritten_sections": [
    {{"section": "string", "original": "string", "rewritten": "string", "reason": "string"}}
  ],
  "full_rewritten_resume": "string (plain text, full resume)",
  "projected_score": 0
}}
"""
    return system, user
