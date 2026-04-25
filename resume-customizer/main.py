"""
Run:
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
from dotenv import load_dotenv
load_dotenv()

from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from agents import Runner
from chatkit.agents import AgentContext, simple_to_agent_input, stream_agent_response

from chatkit.server import ChatKitServer, StreamingResult
from chatkit.types import ThreadMetadata, ThreadStreamEvent, UserMessageItem

from chatkit_store import ResumeCustomizerChatKitStore
from agents_resume_customizer import (
    detect_job_description,
    generate_custom_resume_content,
    load_resume_template_data,
    router_agent,
)

app = FastAPI() 
CUSTOM_RESUME_BY_THREAD: dict[str, dict] = {}


def _extract_user_text(message: UserMessageItem | None) -> str:
    if message is None:
        return ""
    parts: list[str] = []
    for part in message.content:
        if getattr(part, "type", None) == "input_text":
            text = (getattr(part, "text", "") or "").strip()
            if text:
                parts.append(text)
    return "\n".join(parts).strip()


class ResumeCustomizerChatkitServer(ChatKitServer[dict]):
    
    async def respond(self, thread: ThreadMetadata, input_user_message: UserMessageItem | None, context: dict) -> AsyncIterator[ThreadStreamEvent]:
        user_text = _extract_user_text(input_user_message)
        if user_text:
            try:
                target_ids, _ = load_resume_template_data()
                jd_decision = await detect_job_description(user_text)
                likely_jd_by_shape = len(user_text) >= 450
                should_customize = jd_decision.is_job_description and jd_decision.confidence >= 0.50
                if should_customize or likely_jd_by_shape:
                    custom_content = await generate_custom_resume_content(user_text)
                    CUSTOM_RESUME_BY_THREAD[thread.id] = {
                        "target_ids": target_ids,
                        "content": custom_content,
                    }
                    context["resume_customized"] = True
                    context["resume_customized_thread_id"] = thread.id
            except Exception as exc:
                # Non-fatal: conversation should still continue if customization fails.
                print(f"Customization pipeline error for thread {thread.id}: {exc}")
        
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

store = ResumeCustomizerChatKitStore()
server = ResumeCustomizerChatkitServer(store=store)


@app.post("/chatkit") 
async def chatkit(request: Request): 
    result = await server.process(request=await request.body(), context={})
    if isinstance(result, StreamingResult):
        return StreamingResponse(result, media_type="text/event-stream")
    return Response(content=result.json, media_type="application/json")


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


@app.get("/api/base-resume")
async def get_base_resume():
    target_ids, content = load_resume_template_data()
    return JSONResponse(content={"target_ids": target_ids, "content": content})


app.mount("/", StaticFiles(directory="static", html=True), name="static")
