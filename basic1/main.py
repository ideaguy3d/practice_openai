"""
Run:
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

from collections import defaultdict
from datetime import datetime
from typing import AsyncIterator

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from agents import Agent, Runner
from chatkit.agents import AgentContext, simple_to_agent_input, stream_agent_response

from chatkit.server import ChatKitServer, StreamingResult
from chatkit.store import NotFoundError, Store
from chatkit.types import (
    AssistantMessageContent,
    AssistantMessageItem,
    Attachment,
    Page,
    ThreadItem,
    ThreadItemDoneEvent,
    ThreadMetadata,
    ThreadStreamEvent,
    UserMessageItem,
)

from multi_agent_practice import triage_agent


app = FastAPI()

assistant = Agent(
    name="assistant",
    instructions="You are a helpful assistant.",
    model="gpt-4.1-mini",
)


class MyChatKitStore(Store[dict]):
    def __init__(self):
        self.threads: dict[str, ThreadMetadata] = {}
        self.items: dict[str, list[ThreadItem]] = defaultdict(list)

    async def load_thread(self, thread_id: str, context: dict) -> ThreadMetadata:
        if thread_id not in self.threads:
            raise NotFoundError(f"Thread {thread_id} not found")
        return self.threads[thread_id]

    async def save_thread(self, thread: ThreadMetadata, context: dict) -> None:
        self.threads[thread.id] = thread

    async def load_threads(
        self, limit: int, after: str | None, order: str, context: dict
    ) -> Page[ThreadMetadata]:
        threads = list(self.threads.values())
        return self._paginate(
            threads,
            after,
            limit,
            order,
            sort_key=lambda t: t.created_at,
            cursor_key=lambda t: t.id,
        )

    async def load_thread_items(
        self, thread_id: str, after: str | None, limit: int, order: str, context: dict
    ) -> Page[ThreadItem]:
        items = self.items.get(thread_id, [])
        return self._paginate(
            items,
            after,
            limit,
            order,
            sort_key=lambda i: i.created_at,
            cursor_key=lambda i: i.id,
        )

    async def add_thread_item(self, thread_id: str, item: ThreadItem, context: dict) -> None:
        self.items[thread_id].append(item)

    async def save_item(self, thread_id: str, item: ThreadItem, context: dict) -> None:
        items = self.items[thread_id]
        for idx, existing in enumerate(items):
            if existing.id == item.id:
                items[idx] = item
                return
        items.append(item)

    async def load_item(self, thread_id: str, item_id: str, context: dict) -> ThreadItem:
        for item in self.items.get(thread_id, []):
            if item.id == item_id:
                return item
        raise NotFoundError(f"Item {item_id} not found in thread {thread_id}")

    async def delete_thread(self, thread_id: str, context: dict) -> None:
        self.threads.pop(thread_id, None)
        self.items.pop(thread_id, None)

    async def delete_thread_item(self, thread_id: str, item_id: str, context: dict) -> None:
        self.items[thread_id] = [
            item for item in self.items.get(thread_id, []) if item.id != item_id
        ]

    async def save_attachment(self, attachment: Attachment, context: dict) -> None:
        raise NotImplementedError()

    async def load_attachment(self, attachment_id: str, context: dict) -> Attachment:
        raise NotImplementedError()

    async def delete_attachment(self, attachment_id: str, context: dict) -> None:
        raise NotImplementedError()

    def _paginate(self, rows: list, after: str | None, limit: int, order: str, sort_key, cursor_key):
        sorted_rows = sorted(rows, key=sort_key, reverse=(order == "desc"))
        start = 0
        if after:
            for idx, row in enumerate(sorted_rows):
                if cursor_key(row) == after:
                    start = idx + 1
                    break
        data = sorted_rows[start:start + limit]
        has_more = start + limit < len(sorted_rows)
        next_after = cursor_key(data[-1]) if has_more and data else None
        return Page(data=data, has_more=has_more, after=next_after)


class MyChatKitServer(ChatKitServer[dict]):
    async def respond(
        self,
        thread: ThreadMetadata,
        input_user_message: UserMessageItem | None,
        context: dict,
    ) -> AsyncIterator[ThreadStreamEvent]:
       # Convert recent thread items (which includes the user message) to model input
        items_page = await self.store.load_thread_items(
            thread.id,
            after=None,
            limit=20,
            order="asc",
            context=context,
        )
        input_items = await simple_to_agent_input(items_page.data)

        # Stream the run through ChatKit events
        agent_context = AgentContext(thread=thread, store=self.store, request_context=context)
        result = Runner.run_streamed(triage_agent, input_items, context=agent_context)
        async for event in stream_agent_response(agent_context, result):
            yield event


# Create server by passing a store implementation.
store = MyChatKitStore()
server = MyChatKitServer(store=store)


@app.post("/chatkit")
async def chatkit(request: Request):
    result = await server.process(await request.body(), context={})
    if isinstance(result, StreamingResult):
        return StreamingResponse(result, media_type="text/event-stream")
    return Response(content=result.json, media_type="application/json")


app.mount("/", StaticFiles(directory="static", html=True), name="static")
