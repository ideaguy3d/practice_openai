"""
Resume-customizer agents and helper routines.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json

from pydantic import BaseModel, Field
from agents import Agent, AgentOutputSchema, RunContextWrapper, function_tool
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX

_RESUME_CONTENT_PATH = Path(__file__).resolve().parent / "static" / "resume-content.json"
CUSTOM_RESUME_BY_THREAD: dict[str, dict] = {}
LATEST_CUSTOM_RESUME_THREAD_ID: str | None = None


class JobDescriptionDecision(BaseModel):
    is_job_description: bool
    confidence: float = Field(ge=0, le=1)
    reason: str


class ResumeContentUpdates(BaseModel):
    updates: dict[str, str]
    notes: str = ""


def _sanitize_updates(base_content: dict[str, str], updates: dict[str, str], allowed_ids: list[str]) -> dict[str, str]:
    allowed = set(allowed_ids)
    merged = dict(base_content)
    for key, value in updates.items():
        if key not in allowed:
            continue
        cleaned = " ".join(str(value).split()).strip()
        if not cleaned:
            continue
        # Keep fields bounded so rendering remains stable.
        if key == "summary-text":
            merged[key] = cleaned[:550]
        elif key.endswith("-title"):
            merged[key] = cleaned[:90]
        elif key.endswith("-dates"):
            merged[key] = cleaned[:100]
        elif "-bullet-" in key:
            merged[key] = cleaned[:420]
        elif key.startswith("skill-"):
            merged[key] = cleaned[:80]
        else:
            merged[key] = cleaned[:420]
    return merged


def _load_resume_template_data() -> tuple[list[str], dict[str, str]]:
    payload = json.loads(_RESUME_CONTENT_PATH.read_text(encoding="utf-8"))
    content = payload.get("content", {})
    target_ids = list(content.keys())
    return target_ids, content


@function_tool 
def load_resume_template_data() -> tuple[list[str], dict[str, str]]:
    """Load the resume template field ids and current content."""
    return _load_resume_template_data()


def save_custom_resume_for_thread(thread_id: str, updates: dict[str, str]) -> dict:
    global LATEST_CUSTOM_RESUME_THREAD_ID

    target_ids, base_content = _load_resume_template_data()
    content = _sanitize_updates(base_content, updates, target_ids)
    payload = {
        "target_ids": target_ids,
        "content": content,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    CUSTOM_RESUME_BY_THREAD[thread_id] = payload
    LATEST_CUSTOM_RESUME_THREAD_ID = thread_id
    return payload


def get_latest_custom_resume() -> dict | None:
    if not LATEST_CUSTOM_RESUME_THREAD_ID:
        return None
    payload = CUSTOM_RESUME_BY_THREAD.get(LATEST_CUSTOM_RESUME_THREAD_ID)
    if not payload:
        return None
    return {
        "thread_id": LATEST_CUSTOM_RESUME_THREAD_ID,
        **payload,
    }


@function_tool(strict_mode=False)
def save_custom_resume(ctx: RunContextWrapper[object], updates: dict[str, str]) -> dict:
    """Save sanitized custom resume updates for the current chat thread."""
    thread = getattr(ctx.context, "thread", None)
    thread_id = getattr(thread, "id", None)
    if not thread_id:
        return {"saved": False, "error": "thread_id_unavailable"}

    save_custom_resume_for_thread(thread_id, updates)
    return {"saved": True, "thread_id": thread_id, "updated_fields": len(updates)}


jd_detector_agent = Agent(
    name="Job Description Detector",
    handoff_description=(
        "Classifies whether the user's latest message contains a real job description "
        "or job posting for resume tailoring."
    ),
    instructions=f"""
{RECOMMENDED_PROMPT_PREFIX}
Classify whether the user's latest message is a job description to tailor a resume to.

Return:
- is_job_description: true only when the message is clearly a job description or posting
- confidence: 0..1
- reason: one short sentence
""",
    output_type=JobDescriptionDecision,
    model="gpt-5.1",
)


job_skills_agent = Agent(
    name="Job Skills Agent",
    handoff_description=(
        "Analyzes a target job description and existing resume content to recommend "
        "truthful target skills for the customized resume."
    ),
    instructions=f"""
{RECOMMENDED_PROMPT_PREFIX}
You are an internal resume-customization specialist.

Given a target job description and the user's existing resume content, identify 8 to 12 target resume skills.

Rules:
- Use only skills supported by the resume content.
- Align phrasing with the job description when truthful.
- Prefer concise skill phrases suitable for skill-1..skill-12 fields.
- Do not invent tools, certifications, domains, or experience.
- Return internal guidance only; do not address the user.
""",
    model="gpt-5.1",
)


job_experience_agent = Agent(
    name="Job Experience Rewrite Agent",
    handoff_description=(
        "Analyzes a target job description and existing resume bullets to recommend "
        "truthful experience rewrites for the customized resume."
    ),
    instructions=f"""
{RECOMMENDED_PROMPT_PREFIX}
You are an internal resume-customization specialist.

Given a target job description and the user's existing resume content, recommend experience bullet rewrites.

Rules:
- Use only existing resume facts.
- Preserve truthful company, date, role, tool, metric, and scope boundaries.
- Key recommendations to existing resume field ids when possible, such as apple-bullet-1.
- Make bullets more relevant to the job description without overfitting or fabrication.
- Return internal guidance only; do not address the user.
""",
    model="gpt-5.1",
)


resume_customizer_agent = Agent(
    name="Resume Content Customizer",
    handoff_description=(
        "Use this when a confirmed job description should be turned into structured "
        "resume content updates using only the existing resume template fields."
    ),
    instructions=f"""
{RECOMMENDED_PROMPT_PREFIX}
You are the workflow manager for full resume customization.

Process:
1. Use load_resume_template_data to load the user's resume field ids and current content.
2. Call analyze_job_skills with the job description and resume content to get internal target-skill guidance.
3. Call analyze_job_experience with the job description and resume content to get internal experience rewrite guidance.
4. Use both specialist results to produce one final ResumeContentUpdates payload.
5. Call save_custom_resume with exactly the same updates you return so the UI can render the customized resume.

Hard rules:
- Use ONLY keys from the loaded 'content' node.
- Do not invent experience, metrics, tools, dates, or scope not implied by provided resume content.
- Keep strong alignment with job-description language while remaining truthful.
- Return only fields that should change as `updates`.
- Specialist outputs are internal only; do not expose their detailed analysis to the user.
- If save_custom_resume reports an error, include a brief save note in `notes`.

Style constraints:
- summary-text: 1-3 concise sentences.
- skill-1..skill-12: short skill phrases.
- *-title fields: short role title.
- *-dates fields: company + dates formatting, concise and truthful.
- *-bullet-* fields: concise impact bullets.
""",
    output_type=AgentOutputSchema(ResumeContentUpdates, strict_json_schema=False),
    model="gpt-5.1",
    tools=[
        load_resume_template_data,
        job_skills_agent.as_tool(
            tool_name="analyze_job_skills",
            tool_description=(
                "Analyze the target job description against the loaded resume content "
                "and return internal guidance for 8 to 12 truthful target skills."
            ),
        ),
        job_experience_agent.as_tool(
            tool_name="analyze_job_experience",
            tool_description=(
                "Analyze the target job description against the loaded resume content "
                "and return internal guidance for truthful experience bullet rewrites."
            ),
        ),
        save_custom_resume,
    ],
)


router_agent = Agent(
    name="Resume Customizer Router Agent",
    instructions="""
You are the conversational assistant for the resume customizer.

Workflow:
- If the user's message clearly looks like a pasted job description or job posting, hand off to resume_customizer_agent.
- If the message is ambiguous, call classify_job_description first. If it is a job description, hand off to resume_customizer_agent.
- Use job_skills_agent only when the user specifically asks to analyze or compare skills outside the full custom-resume flow.
- Use job_experience_agent only when the user specifically asks to rewrite or review experience bullets outside the full custom-resume flow.
- Do not orchestrate skill mapping and experience rewriting yourself during full customization; resume_customizer_agent manages that internally.
- After resume_customizer_agent completes successfully, tell the user the customized resume is ready.

If not enough info is provided, ask only for missing essentials.
""",
    handoff_description="Delegates requests to the right specialist agent",
    tools=[
        jd_detector_agent.as_tool(
            tool_name="classify_job_description",
            tool_description=(
                "Classify whether the user's latest message is a job description "
                "or job posting for resume tailoring."
            ),
        ),
    ],
    handoffs=[resume_customizer_agent, job_skills_agent, job_experience_agent],
    model="gpt-5.1",
)
