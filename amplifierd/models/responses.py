"""Response models for amplifierd API.

Pydantic models for API responses.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel
from pydantic import Field


class MessageResponse(BaseModel):
    """Response representing a message.

    Attributes:
        role: Message role (user, assistant, system)
        content: Message content
        timestamp: Message timestamp
        metadata: Optional message metadata
    """

    role: str = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(..., description="Message timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Optional metadata")


class SessionInfoResponse(BaseModel):
    """Response for session listing.

    Attributes:
        id: Session ID
        profile: Profile name
        created_at: Creation timestamp
        updated_at: Last update timestamp
        message_count: Number of messages in session
    """

    id: str = Field(..., description="Session ID")
    profile: str = Field(..., description="Profile name")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    message_count: int = Field(..., description="Number of messages")


class SessionResponse(BaseModel):
    """Response for full session details.

    Attributes:
        id: Session ID
        profile: Profile name
        context: Session context data
        created_at: Creation timestamp
        updated_at: Last update timestamp
        message_count: Number of messages in session
    """

    id: str = Field(..., description="Session ID")
    profile: str = Field(..., description="Profile name")
    context: dict[str, Any] = Field(..., description="Session context")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    message_count: int = Field(..., description="Number of messages")


class TranscriptResponse(BaseModel):
    """Response for session transcript.

    Attributes:
        session_id: Session ID
        messages: List of messages
    """

    session_id: str = Field(..., description="Session ID")
    messages: list[MessageResponse] = Field(..., description="List of messages")


class StatusResponse(BaseModel):
    """Response for daemon status.

    Attributes:
        status: Status string (e.g., 'running')
        version: Daemon version
        uptime_seconds: Uptime in seconds
    """

    status: str = Field(..., description="Daemon status")
    version: str = Field(..., description="Daemon version")
    uptime_seconds: float = Field(..., description="Uptime in seconds")
