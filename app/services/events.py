import json
from dataclasses import dataclass
from threading import Condition
from typing import Iterator


@dataclass(frozen=True)
class Event:
    id: int
    event_type: str
    conversation_id: str | None
    data: dict[str, object]
    visible_participant_ids: frozenset[str]


class EventBus:
    """Small in-memory event log for one-process hackathon deployments."""

    def __init__(self, retention: int = 300) -> None:
        self._condition = Condition()
        self._events: list[Event] = []
        self._next_id = 1
        self._retention = retention

    def publish(
        self, *, event_type: str, conversation_id: str | None, data: dict[str, object], visible_to: set[str]
    ) -> Event:
        with self._condition:
            event = Event(self._next_id, event_type, conversation_id, data, frozenset(visible_to))
            self._next_id += 1
            self._events.append(event)
            del self._events[:-self._retention]
            self._condition.notify_all()
            return event

    def stream(self, participant_id: str, after_id: int | None) -> Iterator[Event | None]:
        with self._condition:
            if after_id is not None and self._events and after_id < self._events[0].id - 1:
                yield None
            cursor = after_id or 0
        while True:
            with self._condition:
                visible = [event for event in self._events if event.id > cursor and participant_id in event.visible_participant_ids]
                if not visible:
                    self._condition.wait(timeout=15)
                    visible = [event for event in self._events if event.id > cursor and participant_id in event.visible_participant_ids]
                    if not visible:
                        yield Event(0, "ping", None, {}, frozenset())
                        continue
            for event in visible:
                cursor = event.id
                yield event


def encode_sse(event: Event | None) -> str:
    if event is None:
        return "event: message\ndata: {\"type\":\"sync.required\"}\n\n"
    if event.event_type == "ping":
        return ": ping\n\n"
    payload = {"id": f"evt_{event.id:06d}", "type": event.event_type, "conversationId": event.conversation_id, "data": event.data}
    return f"id: {event.id}\nevent: message\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
