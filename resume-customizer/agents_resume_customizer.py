"""
Resume-customizer agents and helper routines.
"""

from __future__ import annotations

from pathlib import Path
import json

from pydantic import BaseModel, Field
from agents import Agent, Runner, function_tool

_RESUME_CONTENT_PATH = Path(__file__).resolve().parent / "static" / "resume-content.json"


class JobDescriptionDecision(BaseModel):
    is_job_description: bool
    confidence: float = Field(ge=0, le=1)
    reason: str


class ResumeContentUpdates(BaseModel):
    updates: dict[str, str]
    notes: str = ""


@function_tool 
def load_resume_template_data() -> tuple[list[str], dict[str, str]]:
    payload = json.loads(_RESUME_CONTENT_PATH.read_text(encoding="utf-8"))
    content = payload.get("content", {})
    target_ids = list(content.keys())
    return target_ids, content



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



jd_detector_agent = Agent(
    name="Job Description Detector",
    instructions="""
Classify whether the user's latest message is a job description to tailor a resume to.

Return:
- is_job_description: true only when the message is clearly a job description or posting
- confidence: 0..1
- reason: one short sentence
""",
    output_type=JobDescriptionDecision,
    model="gpt-5.1",
)


resume_customizer_agent = Agent(
    name="Resume Content Customizer",
    instructions="""
You customize resume content fields for a target job description.
Use load_resume_template_data to get users resume.

Hard rules:
- Use ONLY keys from the `Allowed keys` list supplied in the input.
- Do not invent experience, metrics, tools, dates, or scope not implied by provided resume content.
- Keep strong alignment with JD language while remaining truthful.
- Return only fields that should change as `updates`.

Style constraints:
- summary-text: 1-3 concise sentences.
- skill-1..skill-12: short skill phrases.
- *-title fields: short role title.
- *-dates fields: company + dates formatting, concise and truthful.
- *-bullet-* fields: concise impact bullets.
""",
    output_type=ResumeContentUpdates,
    model="gpt-5.1",
    tools=[load_resume_template_data]
)


job_skills_agent = Agent(
    name="Job Skills Agent",
    handoff_description="Extracts required job skills and maps transferable skills from a resume/profile.",
    instructions="""
Extract top required skills from the job description and map them to likely transferable skills.
Keep the response concise and actionable.
""",
    model="gpt-5.1",
)


job_experience_agent = Agent(
    name="Job Experience Rewrite Agent",
    handoff_description="Rewrites resume bullets while preserving truthfulness.",
    instructions="""
Rewrite requested bullets for stronger relevance to a target role.
Do not fabricate achievements, metrics, tools, or scope.
""",
    model="gpt-5.1",
)


router_agent = Agent(
    name="Resume Customizer Router Agent",
    instructions="""
You are the conversational assistant for the resume customizer.

Use jd_detector_agent to determine if job description was provided, 
If a job description was provided use: 
- resume_customizer_agent, 
- job_skills_agent, 
- job_experience_agent.
If not enough info is provided, ask only for missing essentials.
""",
    handoffs=[jd_detector_agent, resume_customizer_agent, job_skills_agent, job_experience_agent],
    model="gpt-5.1",
)