"""
In-memory ChatKit store used by the resume-customizer demo app.

This implementation is intentionally simple:
- Thread metadata is kept in `self.threads`
- Thread items/messages are kept in `self.items`
- Data is lost when the process restarts
"""

from collections import defaultdict
from chatkit.store import NotFoundError, Store
from chatkit.types import (
    Attachment,
    Page,
    ThreadItem,
    ThreadMetadata,
)


class ResumeCustomizerChatKitStore(Store[dict]):
    """Minimal in-memory implementation of the ChatKit `Store` interface."""

    def __init__(self):
        """Initialize in-memory containers for threads and thread items."""
        self.threads: dict[str, ThreadMetadata] = {}
        self.items: dict[str, list[ThreadItem]] = defaultdict(list)

    async def load_thread(self, thread_id: str, context: dict) -> ThreadMetadata:
        """Return one thread by id, or raise if it does not exist."""
        if thread_id not in self.threads:
            raise NotFoundError(f"Thread {thread_id} not found")
        return self.threads[thread_id]

    async def save_thread(self, thread: ThreadMetadata, context: dict) -> None:
        """Create or overwrite a thread record."""
        self.threads[thread.id] = thread

    async def load_threads(self, limit: int, after: str | None, order: str, context: dict) -> Page[ThreadMetadata]:
        """Return paginated thread metadata sorted by thread creation time."""
        threads = list(self.threads.values())
        return self._paginate(
            threads,
            after,
            limit,
            order,
            sort_key=lambda t: t.created_at,
            cursor_key=lambda t: t.id,
        )

    async def load_thread_items(self, thread_id: str, after: str | None, limit: int, order: str, context: dict) -> Page[ThreadItem]:
        """Return paginated items/messages for one thread."""
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
        """Append a new item/message to a thread."""
        self.items[thread_id].append(item)

    async def save_item(self, thread_id: str, item: ThreadItem, context: dict) -> None:
        """Update an existing item by id, or append if not found."""
        items = self.items[thread_id]
        for idx, existing in enumerate(items):
            if existing.id == item.id:
                items[idx] = item
                return
        items.append(item)

    async def load_item(self, thread_id: str, item_id: str, context: dict) -> ThreadItem:
        """Load one item from a thread by item id."""
        for item in self.items.get(thread_id, []):
            if item.id == item_id:
                return item
        raise NotFoundError(f"Item {item_id} not found in thread {thread_id}")

    async def delete_thread(self, thread_id: str, context: dict) -> None:
        """Delete a thread and all its items if they exist."""
        self.threads.pop(thread_id, None)
        self.items.pop(thread_id, None)

    async def delete_thread_item(self, thread_id: str, item_id: str, context: dict) -> None:
        """Delete one item from a thread by filtering it out."""
        self.items[thread_id] = [
            item for item in self.items.get(thread_id, []) if item.id != item_id
        ]

    async def save_attachment(self, attachment: Attachment, context: dict) -> None:
        """Attachments are not implemented in this demo store."""
        raise NotImplementedError()

    async def load_attachment(self, attachment_id: str, context: dict) -> Attachment:
        """Attachments are not implemented in this demo store."""
        raise NotImplementedError()

    async def delete_attachment(self, attachment_id: str, context: dict) -> None:
        """Attachments are not implemented in this demo store."""
        raise NotImplementedError()

    def _paginate(self, rows: list, after: str | None, limit: int, order: str, sort_key, cursor_key):
        """Generic cursor-based pagination helper used by threads and items.

        `after` is treated as the cursor of the last item from the previous page.
        """
        # Sort ascending or descending depending on requested order.
        sorted_rows = sorted(rows, key=sort_key, reverse=(order == "desc"))
        start = 0
        if after:
            # Find the cursor row, then start from the next row.
            for idx, row in enumerate(sorted_rows):
                if cursor_key(row) == after:
                    start = idx + 1
                    break
        # Slice the requested page window.
        data = sorted_rows[start:start + limit]
        has_more = start + limit < len(sorted_rows)
        # Cursor for the next page is the last row returned on this page.
        next_after = cursor_key(data[-1]) if has_more and data else None
        return Page(data=data, has_more=has_more, after=next_after)
