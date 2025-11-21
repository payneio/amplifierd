"""Module discovery API endpoints."""

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from pydantic import BaseModel

from ..models import ModuleDetails
from ..models import ModuleInfo
from ..services import ModuleDiscoveryService

router = APIRouter(prefix="/api/v1/modules", tags=["modules"])


class ModuleSourceRequest(BaseModel):
    """Request body for module source operations."""

    source: str
    scope: str = "project"


def get_module_discovery_service() -> ModuleDiscoveryService:
    """Get module discovery service instance.

    Returns:
        ModuleDiscoveryService instance
    """
    return ModuleDiscoveryService()


@router.get("/", response_model=list[ModuleInfo])
async def list_modules(
    service: Annotated[ModuleDiscoveryService, Depends(get_module_discovery_service)],
    type: Annotated[str | None, Query(description="Filter by module type")] = None,
) -> list[ModuleInfo]:
    """List modules with optional type filter.

    Args:
        service: Module discovery service instance
        type: Optional module type filter (provider, hook, tool, orchestrator)

    Returns:
        List of module information
    """
    modules = await service.list_all_modules(type_filter=type)
    return [ModuleInfo(**m) for m in modules]  # pyright: ignore[reportArgumentType]


@router.get("/providers", response_model=list[ModuleInfo])
async def list_providers(
    service: Annotated[ModuleDiscoveryService, Depends(get_module_discovery_service)],
) -> list[ModuleInfo]:
    """List provider modules.

    Args:
        service: Module discovery service instance

    Returns:
        List of provider module information
    """
    modules = await service.list_providers()
    return [ModuleInfo(**m) for m in modules]  # pyright: ignore[reportArgumentType]


@router.get("/hooks", response_model=list[ModuleInfo])
async def list_hooks(
    service: Annotated[ModuleDiscoveryService, Depends(get_module_discovery_service)],
) -> list[ModuleInfo]:
    """List hook modules.

    Args:
        service: Module discovery service instance

    Returns:
        List of hook module information
    """
    modules = await service.list_hooks()
    return [ModuleInfo(**m) for m in modules]  # pyright: ignore[reportArgumentType]


@router.get("/tools", response_model=list[ModuleInfo])
async def list_tools(
    service: Annotated[ModuleDiscoveryService, Depends(get_module_discovery_service)],
) -> list[ModuleInfo]:
    """List tool modules.

    Args:
        service: Module discovery service instance

    Returns:
        List of tool module information
    """
    modules = await service.list_tools()
    return [ModuleInfo(**m) for m in modules]  # pyright: ignore[reportArgumentType]


@router.get("/orchestrators", response_model=list[ModuleInfo])
async def list_orchestrators(
    service: Annotated[ModuleDiscoveryService, Depends(get_module_discovery_service)],
) -> list[ModuleInfo]:
    """List orchestrator modules.

    Args:
        service: Module discovery service instance

    Returns:
        List of orchestrator module information
    """
    modules = await service.list_orchestrators()
    return [ModuleInfo(**m) for m in modules]  # pyright: ignore[reportArgumentType]


@router.get("/{module_id}", response_model=ModuleDetails)
async def get_module(
    module_id: str,
    service: Annotated[ModuleDiscoveryService, Depends(get_module_discovery_service)],
) -> ModuleDetails:
    """Get module details by ID.

    Args:
        module_id: Module identifier
        service: Module discovery service instance

    Returns:
        Module details

    Raises:
        HTTPException: 404 if module not found, 500 for other errors
    """
    try:
        module = await service.get_module_details(module_id)
        return ModuleDetails(**module)  # pyright: ignore[reportArgumentType]
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{module_id}/sources", status_code=201)
async def add_module_source(
    module_id: str,
    request: ModuleSourceRequest,
    service: Annotated[ModuleDiscoveryService, Depends(get_module_discovery_service)],
) -> dict[str, str]:
    """Add a module source override.

    Args:
        module_id: Module identifier
        request: Module source request
        service: Module discovery service instance

    Returns:
        Module source details

    Raises:
        HTTPException: 500 for errors
    """
    try:
        return await service.add_module_source(module_id, request.source, request.scope)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to add module source: {str(exc)}") from exc


@router.put("/{module_id}/sources", status_code=200)
async def update_module_source(
    module_id: str,
    request: ModuleSourceRequest,
    service: Annotated[ModuleDiscoveryService, Depends(get_module_discovery_service)],
) -> dict[str, str]:
    """Update a module source override.

    Args:
        module_id: Module identifier
        request: Module source request
        service: Module discovery service instance

    Returns:
        Module source details

    Raises:
        HTTPException: 500 for errors
    """
    try:
        return await service.update_module_source(module_id, request.source, request.scope)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update module source: {str(exc)}") from exc


@router.delete("/{module_id}/sources", status_code=200)
async def remove_module_source(
    module_id: str,
    service: Annotated[ModuleDiscoveryService, Depends(get_module_discovery_service)],
    scope: str = "project",
) -> dict[str, bool]:
    """Remove a module source override.

    Args:
        module_id: Module identifier
        scope: Configuration scope (user/project/local)
        service: Module discovery service instance

    Returns:
        Removal status

    Raises:
        HTTPException: 404 if source override not found, 500 for other errors
    """
    try:
        return await service.remove_module_source(module_id, scope)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to remove module source: {str(exc)}") from exc


# Type-specific convenience endpoints


# PROVIDERS
@router.post("/providers/{module_id}/sources", status_code=201)
async def add_provider_source(
    module_id: str,
    request: ModuleSourceRequest,
    service: Annotated[ModuleDiscoveryService, Depends(get_module_discovery_service)],
) -> dict[str, str]:
    """Add a provider module source override."""
    return await add_module_source(module_id, request, service)


@router.put("/providers/{module_id}/sources", status_code=200)
async def update_provider_source(
    module_id: str,
    request: ModuleSourceRequest,
    service: Annotated[ModuleDiscoveryService, Depends(get_module_discovery_service)],
) -> dict[str, str]:
    """Update a provider module source override."""
    return await update_module_source(module_id, request, service)


@router.delete("/providers/{module_id}/sources", status_code=200)
async def remove_provider_source(
    module_id: str,
    service: Annotated[ModuleDiscoveryService, Depends(get_module_discovery_service)],
    scope: str = "project",
) -> dict[str, bool]:
    """Remove a provider module source override."""
    return await remove_module_source(module_id, service, scope)


# HOOKS
@router.post("/hooks/{module_id}/sources", status_code=201)
async def add_hook_source(
    module_id: str,
    request: ModuleSourceRequest,
    service: Annotated[ModuleDiscoveryService, Depends(get_module_discovery_service)],
) -> dict[str, str]:
    """Add a hook module source override."""
    return await add_module_source(module_id, request, service)


@router.put("/hooks/{module_id}/sources", status_code=200)
async def update_hook_source(
    module_id: str,
    request: ModuleSourceRequest,
    service: Annotated[ModuleDiscoveryService, Depends(get_module_discovery_service)],
) -> dict[str, str]:
    """Update a hook module source override."""
    return await update_module_source(module_id, request, service)


@router.delete("/hooks/{module_id}/sources", status_code=200)
async def remove_hook_source(
    module_id: str,
    service: Annotated[ModuleDiscoveryService, Depends(get_module_discovery_service)],
    scope: str = "project",
) -> dict[str, bool]:
    """Remove a hook module source override."""
    return await remove_module_source(module_id, service, scope)


# TOOLS
@router.post("/tools/{module_id}/sources", status_code=201)
async def add_tool_source(
    module_id: str,
    request: ModuleSourceRequest,
    service: Annotated[ModuleDiscoveryService, Depends(get_module_discovery_service)],
) -> dict[str, str]:
    """Add a tool module source override."""
    return await add_module_source(module_id, request, service)


@router.put("/tools/{module_id}/sources", status_code=200)
async def update_tool_source(
    module_id: str,
    request: ModuleSourceRequest,
    service: Annotated[ModuleDiscoveryService, Depends(get_module_discovery_service)],
) -> dict[str, str]:
    """Update a tool module source override."""
    return await update_module_source(module_id, request, service)


@router.delete("/tools/{module_id}/sources", status_code=200)
async def remove_tool_source(
    module_id: str,
    service: Annotated[ModuleDiscoveryService, Depends(get_module_discovery_service)],
    scope: str = "project",
) -> dict[str, bool]:
    """Remove a tool module source override."""
    return await remove_module_source(module_id, service, scope)


# ORCHESTRATORS
@router.post("/orchestrators/{module_id}/sources", status_code=201)
async def add_orchestrator_source(
    module_id: str,
    request: ModuleSourceRequest,
    service: Annotated[ModuleDiscoveryService, Depends(get_module_discovery_service)],
) -> dict[str, str]:
    """Add an orchestrator module source override."""
    return await add_module_source(module_id, request, service)


@router.put("/orchestrators/{module_id}/sources", status_code=200)
async def update_orchestrator_source(
    module_id: str,
    request: ModuleSourceRequest,
    service: Annotated[ModuleDiscoveryService, Depends(get_module_discovery_service)],
) -> dict[str, str]:
    """Update an orchestrator module source override."""
    return await update_module_source(module_id, request, service)


@router.delete("/orchestrators/{module_id}/sources", status_code=200)
async def remove_orchestrator_source(
    module_id: str,
    service: Annotated[ModuleDiscoveryService, Depends(get_module_discovery_service)],
    scope: str = "project",
) -> dict[str, bool]:
    """Remove an orchestrator module source override."""
    return await remove_module_source(module_id, service, scope)
