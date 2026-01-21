"""
USYC Protocol Labs - Base Agent
Abstract base class for all agents in the system.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
import asyncio

from .event_bus import EventBus, Event, EventType, event_bus


class BaseAgent(ABC):
    """
    Abstract base class for agents.
    Provides common functionality for event handling and lifecycle management.
    """

    def __init__(self, name: str, event_bus_instance: Optional[EventBus] = None):
        """
        Initialize the base agent.

        Args:
            name: Unique name for this agent
            event_bus_instance: Optional custom event bus (uses global by default)
        """
        self.name = name
        self.event_bus = event_bus_instance or event_bus
        self._running = False
        self._started_at: Optional[datetime] = None

    @property
    def is_running(self) -> bool:
        """Check if agent is currently running."""
        return self._running

    @property
    def uptime(self) -> Optional[float]:
        """Get agent uptime in seconds."""
        if not self._started_at:
            return None
        return (datetime.utcnow() - self._started_at).total_seconds()

    async def start(self) -> None:
        """Start the agent and register event handlers."""
        if self._running:
            return

        self._running = True
        self._started_at = datetime.utcnow()

        await self._register_handlers()
        await self._on_start()

        await self.event_bus.publish(Event(
            event_type=EventType.AGENT_STARTED,
            data={"agent_name": self.name},
            source_agent=self.name,
        ))

        print(f"[{self.name}] Agent started")

    async def stop(self) -> None:
        """Stop the agent and unregister event handlers."""
        if not self._running:
            return

        await self._on_stop()
        self._running = False

        await self.event_bus.publish(Event(
            event_type=EventType.AGENT_STOPPED,
            data={"agent_name": self.name, "uptime": self.uptime},
            source_agent=self.name,
        ))

        print(f"[{self.name}] Agent stopped")

    async def emit(self, event_type: EventType, data: dict) -> None:
        """
        Emit an event from this agent.

        Args:
            event_type: The type of event
            data: Event data payload
        """
        event = Event(
            event_type=event_type,
            data=data,
            source_agent=self.name,
        )
        await self.event_bus.publish(event)

    def subscribe(self, event_type: EventType, handler) -> None:
        """
        Subscribe to an event type.

        Args:
            event_type: The type of event to listen for
            handler: Handler function
        """
        self.event_bus.subscribe(event_type, handler)

    @abstractmethod
    async def _register_handlers(self) -> None:
        """Register event handlers. Override in subclasses."""
        pass

    async def _on_start(self) -> None:
        """Called when agent starts. Override for custom startup logic."""
        pass

    async def _on_stop(self) -> None:
        """Called when agent stops. Override for custom shutdown logic."""
        pass
