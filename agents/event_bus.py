"""
USYC Protocol Labs - Event Bus
Pub/Sub communication system for inter-agent messaging.
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4


class EventType(Enum):
    """Supported event types in the system."""
    DEPOSIT_INITIATED = "deposit_initiated"
    DEPOSIT_COMPLETED = "deposit_completed"
    DEPOSIT_FAILED = "deposit_failed"
    WITHDRAW_INITIATED = "withdraw_initiated"
    WITHDRAW_COMPLETED = "withdraw_completed"
    WITHDRAW_FAILED = "withdraw_failed"
    COMPOUND_INITIATED = "compound_initiated"
    COMPOUND_COMPLETED = "compound_completed"
    COMPOUND_FAILED = "compound_failed"
    RECEIPT_GENERATED = "receipt_generated"
    AGENT_STARTED = "agent_started"
    AGENT_STOPPED = "agent_stopped"


@dataclass
class Event:
    """Event object for inter-agent communication."""
    event_type: EventType
    data: Dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source_agent: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "source_agent": self.source_agent,
        }


class EventBus:
    """
    Central event bus for publish/subscribe communication between agents.
    Thread-safe and supports async handlers.
    """

    _instance: Optional["EventBus"] = None

    def __new__(cls) -> "EventBus":
        """Singleton pattern for global event bus."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._subscribers: Dict[EventType, List[Callable]] = {}
        self._event_history: List[Event] = []
        self._max_history: int = 1000
        self._initialized = True

    def subscribe(self, event_type: EventType, handler: Callable) -> None:
        """
        Subscribe a handler to an event type.

        Args:
            event_type: The type of event to listen for
            handler: Async or sync callable to handle the event
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: Callable) -> None:
        """
        Unsubscribe a handler from an event type.

        Args:
            event_type: The type of event
            handler: The handler to remove
        """
        if event_type in self._subscribers:
            if handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)

    async def publish(self, event: Event) -> None:
        """
        Publish an event to all subscribers.

        Args:
            event: The event to publish
        """
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

        if event.event_type not in self._subscribers:
            return

        handlers = self._subscribers[event.event_type]
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                print(f"[EventBus] Error in handler for {event.event_type.value}: {e}")

    def get_history(
        self,
        event_type: Optional[EventType] = None,
        limit: int = 100
    ) -> List[Event]:
        """
        Get event history, optionally filtered by type.

        Args:
            event_type: Optional filter by event type
            limit: Maximum number of events to return

        Returns:
            List of events
        """
        events = self._event_history
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events[-limit:]

    def clear_history(self) -> None:
        """Clear all event history."""
        self._event_history.clear()

    def reset(self) -> None:
        """Reset the event bus (clear subscribers and history)."""
        self._subscribers.clear()
        self._event_history.clear()


# Global event bus instance
event_bus = EventBus()
