"""
Run:
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
from dotenv import load_dotenv
load_dotenv()

from types import SimpleNamespace
from typing import AsyncIterator
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agents import Runner
from chatkit.agents import AgentContext, simple_to_agent_input, stream_agent_response

from chatkit.server import ChatKitServer, StreamingResult
from chatkit.types import ThreadMetadata, ThreadStreamEvent, UserMessageItem

from chatkit_store import ResumeCustomizerChatKitStore
from agents_resume_customizer import (
    CUSTOM_RESUME_BY_THREAD,
    ResumeContentUpdates,
    get_latest_custom_resume,
    router_agent,
    save_custom_resume_for_thread,
)

should_log = True

app = FastAPI()


class CustomizeResumeRequest(BaseModel):
    job_description: str
    thread_id: str | None = None


def log(msg):
    s = "\n\n--\n\n"
    open("app.log", "a").write(s + msg + s)


class ResumeCustomizerChatkitServer(ChatKitServer[dict]):

    async def respond(self, thread: ThreadMetadata, input_user_message: UserMessageItem | None, context: dict) -> AsyncIterator[ThreadStreamEvent]:
        # Load the latest N items, then reorder to chronological for model input.
        # This avoids dropping recent context once thread length exceeds N.
        items = await self.store.load_thread_items(
            thread.id,
            after=None,
            limit=20,
            order="desc",
            context=context,
        )
        recent_items_in_order = list(reversed(items.data))
        input_items = await simple_to_agent_input(recent_items_in_order)

        # Stream via ChatKit events 
        agent_context = AgentContext(thread=thread, store=self.store, request_context=context)
        result = Runner.run_streamed(starting_agent=router_agent, input=input_items, context=agent_context)
        async for event in stream_agent_response(context=agent_context, result=result):
            yield event 
        if isinstance(result.final_output, ResumeContentUpdates):
            save_custom_resume_for_thread(thread.id, result.final_output.updates)

store = ResumeCustomizerChatKitStore()
server = ResumeCustomizerChatkitServer(store=store)


@app.post("/chatkit") 
async def chatkit(request: Request): 
    result = await server.process(request=await request.body(), context={})
    if isinstance(result, StreamingResult):
        return StreamingResponse(result, media_type="text/event-stream")
    return Response(content=result.json, media_type="application/json")


@app.post("/api/customize-resume")
async def customize_resume(request: CustomizeResumeRequest):
    job_description = request.job_description.strip()
    if not job_description:
        return JSONResponse(status_code=400, content={"error": "job_description_required"})

    thread_id = request.thread_id or f"fallback-{uuid4().hex}"
    agent_context = SimpleNamespace(thread=SimpleNamespace(id=thread_id))
    result = await Runner.run(
        starting_agent=router_agent,
        input=job_description,
        context=agent_context,
        max_turns=10,
    )
    if isinstance(result.final_output, ResumeContentUpdates):
        save_custom_resume_for_thread(thread_id, result.final_output.updates)

    payload = CUSTOM_RESUME_BY_THREAD.get(thread_id)
    if not payload:
        return JSONResponse(status_code=500, content={"error": "custom_resume_not_saved"})
    return JSONResponse(content={"thread_id": thread_id, **payload})


@app.get("/api/custom-resume/latest")
async def get_latest_custom_resume_response():
    payload = get_latest_custom_resume()
    if not payload:
        return JSONResponse(status_code=404, content={"error": "custom_resume_not_found"})
    return JSONResponse(content=payload)


@app.get("/api/custom-resume/{thread_id}")
async def get_custom_resume(thread_id: str):
    payload = CUSTOM_RESUME_BY_THREAD.get(thread_id)
    if not payload:
        return JSONResponse(status_code=404, content={"error": "custom_resume_not_found"})
    return JSONResponse(content=payload)


@app.get("/api/custom-resume/{thread_id}/exists")
async def custom_resume_exists(thread_id: str):
    thread_exists = thread_id in CUSTOM_RESUME_BY_THREAD
    return JSONResponse(content={"exists": thread_exists})


app.mount("/", StaticFiles(directory="static", html=True), name="static")
