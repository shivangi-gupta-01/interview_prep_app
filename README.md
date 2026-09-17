# AI Interview Coach

A Python (FastAPI) application with three workflows and a tool-using AI coach,
powered by Google Gemini through LangChain:

1. **Role / JD interview prep** — generates a personalized set of technical,
   behavioral, and system-design questions based on role, skills, experience
   level, and (optionally) a pasted job description. Includes a "practice
   this answer" flow that scores your typed answer and shows an improved
   version.
2. **Resume-grounded scenario prep** — upload or paste a resume; the app
   pulls out concrete highlights (projects, metrics, tech) and generates
   situational / "tell me about a time" questions tied to your actual
   experience, with STAR-structured hints.
3. **ATS resume scorer & rewriter** — scores a resume 0–100 across
   parseability, keyword match (vs. a JD if provided), section
   completeness, quantified impact, and clarity — then can rewrite the
   resume section-by-section (and as a full plain-text document) to push
  the score up, without inventing fake experience.
4. **AI Coach agent** - accepts a natural-language request and chooses the
  interview, resume-scenario, ATS-scoring, or ATS-rewriting tool to run.

## Project layout

```
interview_prep_app/
├── app/
│   ├── main.py            # FastAPI app + routes for the UI
│   ├── config.py          # env-driven settings
│   ├── models.py          # Pydantic request/response schemas
│   ├── llm_service.py     # LangChain Gemini model + typed structured calls
│   ├── agent_service.py    # Tool-using LangChain interview coach agent
│   ├── services/           # Shared application services
│   ├── resume_parser.py   # PDF/DOCX/TXT text extraction
│   └── routers/
│       ├── interview.py   # /api/interview/*
│       ├── resume.py      # /api/resume/*  (scenarios)
│       └── ats.py         # /api/ats/*     (scoring + rewrite)
├── templates/index.html   # single-page UI (3 tabs)
├── static/style.css
├── static/app.js
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then paste your GEMINI_API_KEY
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000

### Frontend styling

Tailwind utilities and the small set of component styles are loaded directly
by `templates/index.html`; there is no separate generated CSS build step.

## Run with Docker

```bash
cp .env.example .env        # then paste your GEMINI_API_KEY
docker compose up --build
```

Docker builds the Tailwind stylesheet in a Node build stage, then copies it
into the smaller Python application image. Open http://localhost:8000 after
the container starts. Stop it with `docker compose down`.

## Request workflow

1. The browser loads `/` from `app.main.home`, which renders `templates/index.html`.
2. The browser calls `GET /api/health` to show the configured Gemini model.
3. Interview question form: `POST /api/interview/questions` -> `interview.py` -> prompt builder -> async LangChain Gemini call -> `InterviewSet` response.
4. Answer practice: `POST /api/interview/evaluate` -> answer prompt -> async Gemini call -> `AnswerEvaluation` response.
5. Resume scenarios: `POST /api/resume/scenarios` -> `resume_service.resolve_resume_text` -> `resume_parser.py` for PDF/DOCX/TXT -> scenario prompt -> Gemini -> `ScenarioSet`.
6. ATS score: `POST /api/ats/score` -> shared resume service -> ATS prompt -> Gemini -> `ATSReport`.
7. ATS rewrite: `POST /api/ats/optimize` -> shared resume service plus the previous `ats_report` -> rewrite prompt -> Gemini -> `ATSOptimizeResult`.
8. AI Coach: `POST /api/agent/chat` -> `agent_service.run_agent` -> LangChain agent selects one of four tools -> tool calls the relevant prompt/service -> structured response.

Every Gemini workflow is asynchronous, uses a Pydantic schema for structured
output, and returns HTTP 502 when the external model call fails.

## API reference

All endpoints return JSON and are documented interactively at `/docs`
(Swagger UI) once the server is running.

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/interview/questions` | POST (JSON) | Generate a personalized question set |
| `/api/interview/evaluate` | POST (JSON) | Score a typed answer, get an improved version |
| `/api/resume/scenarios` | POST (multipart: file **or** resume_text) | Resume-grounded scenario questions |
| `/api/ats/score` | POST (multipart: file **or** resume_text, + optional job_description) | ATS score + breakdown |
| `/api/ats/optimize` | POST (multipart, same inputs) | Section-by-section ATS rewrite + full resume text |
| `/api/agent/chat` | POST (JSON) | Agent chooses and runs the best preparation tool |
| `/api/health` | GET | Health check / configured model name |

### Example: generate interview questions

```bash
curl -X POST http://localhost:8000/api/interview/questions \
  -H "Content-Type: application/json" \
  -d '{
    "role": "Backend Engineer",
    "skills": ["Python", "Django", "PostgreSQL", "AWS"],
    "experience_level": "mid",
    "question_mix": "balanced",
    "num_questions": 6
  }'
```

### Example: ATS score with a resume file + JD

```bash
curl -X POST http://localhost:8000/api/ats/score \
  -F "file=@resume.pdf" \
  -F "job_description=$(cat jd.txt)"
```

## Notes / next steps for production

- **Auth & rate limiting**: currently open — add an API-key or session auth
  layer and per-user rate limiting before exposing publicly (e.g. via a
  reverse proxy like nginx/Traefik, or FastAPI middleware + Redis).
- **Persistence**: sessions are stateless right now (nothing is saved to a
  database). For a "save my prep history" feature, add PostgreSQL +
  SQLAlchemy models keyed by user, and store generated question sets,
  scenario sets, and ATS reports.
- **Scanned/image PDFs**: `pypdf` only extracts text layers. Add OCR
  (e.g. `pytesseract`) if you need to support scanned resume images.
- **Model choice**: set `GEMINI_MODEL` in `.env` to whichever model
  alias your account has access to.
- **Structured output**: LangChain maps Gemini responses directly into the
  Pydantic response models, with output length limits and async calls.
- **Observability**: add structured logging + request IDs before
  production use; LLM calls can fail or time out, and `llm_service.py`
  already retries transient errors, but you'll want dashboards.
