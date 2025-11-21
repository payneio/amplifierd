"""Async execution runner for amplifier-core.

Handles executing user prompts and streaming responses.

Contract:
- Inputs: Session objects, user prompts, configuration data
- Outputs: Async stream of execution results
- Side Effects: Creates AmplifierSession, makes LLM calls
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from ..models import Session
from ..sessions.state import add_message

if TYPE_CHECKING:
    from amplifier_core import AmplifierSession

logger = logging.getLogger(__name__)


class ExecutionRunner:
    """Async execution runner using amplifier-core.

    Manages execution lifecycle including:
    - Creating AmplifierSession instances
    - Processing user prompts
    - Streaming responses
    - Tracking execution in session state

    Example:
        >>> import asyncio
        >>> from amplifier_library.sessions import SessionManager
        >>> manager = SessionManager()
        >>> session = manager.create_session("default")
        >>> runner = ExecutionRunner(config={}, search_paths=[])
        >>> async def run():
        ...     async for chunk in runner.execute(session, "Hello"):
        ...         print(chunk, end="")
        >>> asyncio.run(run())
    """

    def __init__(
        self: "ExecutionRunner",
        config: dict[str, Any],
        search_paths: list[Path] | None = None,
    ) -> None:
        """Initialize execution runner.

        Args:
            config: Amplifier configuration dictionary
            search_paths: Optional module search paths
        """
        self.config = config
        self.search_paths = search_paths or []
        self._session: AmplifierSession | None = None

    async def execute(
        self: "ExecutionRunner",
        session: Session,
        user_input: str,
    ) -> str:
        """Execute user input and return response.

        Creates an AmplifierSession if needed, processes the user input,
        and returns the response. Automatically saves messages to session state.

        Note: Streaming is handled by the display_system passed to AmplifierSession,
        not at this layer. This method returns the complete response.

        Args:
            session: Session object
            user_input: User's prompt/message

        Returns:
            Complete response text

        Example:
            >>> import asyncio
            >>> from amplifier_library.sessions import SessionManager
            >>> manager = SessionManager()
            >>> session = manager.create_session("default")
            >>> runner = ExecutionRunner(config={})
            >>> async def run():
            ...     response = await runner.execute(session, "Hello")
            ...     print(response)
            >>> asyncio.run(run())
        """
        # Add user message to session state
        add_message(session, role="user", content=user_input)

        # Create AmplifierSession if needed
        if self._session is None:
            try:
                from amplifier_core import AmplifierSession
            except ImportError as e:
                raise RuntimeError(
                    "amplifier-core is required for execution. Install it with: pip install amplifier-core"
                ) from e

            self._session = AmplifierSession(self.config, session_id=session.id)
            await self._session.initialize()
            logger.info(f"Initialized AmplifierSession for {session.id}")

        # Execute and get response
        try:
            response = await self._session.execute(user_input)

            # Add assistant response to session state
            if response:
                add_message(session, role="assistant", content=response)

            return response

        except Exception as e:
            error_msg = f"Execution error: {e!s}"
            logger.error(error_msg)
            add_message(session, role="assistant", content=error_msg)
            return error_msg

    async def cleanup(self: "ExecutionRunner") -> None:
        """Clean up resources.

        Should be called when done with the runner to properly
        close the AmplifierSession.

        Example:
            >>> import asyncio
            >>> runner = ExecutionRunner(config={})
            >>> asyncio.run(runner.cleanup())
        """
        if self._session is not None:
            # AmplifierSession cleanup if needed
            self._session = None
            logger.debug("ExecutionRunner cleaned up")
