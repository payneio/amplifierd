"""API routers for amplifierd daemon.

This module contains FastAPI routers for all API endpoints.
"""

from .collections import router as collections_router
from .messages import router as messages_router
from .modules import router as modules_router
from .profiles import router as profiles_router
from .sessions import router as sessions_router
from .status import router as status_router

__all__ = [
    "sessions_router",
    "messages_router",
    "status_router",
    "profiles_router",
    "collections_router",
    "modules_router",
]
