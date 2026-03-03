"""CLI entry point for amplifierd."""

from __future__ import annotations

import logging

import click

_LOG_LEVELS: dict[str, int] = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


@click.group()
def main() -> None:
    """amplifierd – Amplifier daemon HTTP server."""


@main.command()
@click.option("--host", default=None, type=str, help="Bind host address.")
@click.option("--port", default=None, type=int, help="Bind port number.")
@click.option("--reload", is_flag=True, default=False, help="Enable hot-reload for development.")
@click.option(
    "--log-level",
    default=None,
    type=click.Choice(["debug", "info", "warning", "error"], case_sensitive=False),
    help="Log level (overrides AMPLIFIERD_LOG_LEVEL).",
)
def serve(
    host: str | None,
    port: int | None,
    reload: bool,
    log_level: str | None,
) -> None:
    """Start the amplifierd HTTP server."""
    import uvicorn

    from amplifierd.config import DaemonSettings

    settings = DaemonSettings()

    effective_host = host if host is not None else settings.host
    effective_port = port if port is not None else settings.port
    effective_log_level = log_level if log_level is not None else settings.log_level

    logging.basicConfig(
        level=_LOG_LEVELS.get(effective_log_level.lower(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    click.echo(
        f"amplifierd starting – host={effective_host} port={effective_port} "
        f"log-level={effective_log_level}"
    )

    uvicorn.run(
        "amplifierd.app:create_app",
        host=effective_host,
        port=effective_port,
        reload=reload,
        log_level=effective_log_level,
        factory=True,
    )


if __name__ == "__main__":
    main()
