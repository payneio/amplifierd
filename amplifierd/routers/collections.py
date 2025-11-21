"""Collection management API endpoints."""

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from pydantic import BaseModel

from ..models import CollectionDetails
from ..models import CollectionInfo
from ..services import CollectionService

router = APIRouter(prefix="/api/v1/collections", tags=["collections"])


class MountCollectionRequest(BaseModel):
    """Request body for mounting a collection."""

    identifier: str
    source: str


def get_collection_service() -> CollectionService:
    """Get collection service instance.

    Returns:
        CollectionService instance
    """
    return CollectionService()


@router.get("/", response_model=list[CollectionInfo])
async def list_collections(
    service: Annotated[CollectionService, Depends(get_collection_service)],
) -> list[CollectionInfo]:
    """List all available collections.

    Args:
        service: Collection service instance

    Returns:
        List of collection information
    """
    collections = await service.list_collections()
    return [CollectionInfo(**c) for c in collections]


@router.get("/{identifier:path}", response_model=CollectionDetails)
async def get_collection(
    identifier: str,
    service: Annotated[CollectionService, Depends(get_collection_service)],
) -> CollectionDetails:
    """Get collection details by identifier.

    Args:
        identifier: Collection identifier
        service: Collection service instance

    Returns:
        Collection details

    Raises:
        HTTPException: 404 if collection not found, 500 for other errors
    """
    try:
        collection = await service.get_collection(identifier)
        return CollectionDetails(**collection)  # pyright: ignore[reportArgumentType]
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/", status_code=201)
async def mount_collection(
    request: MountCollectionRequest,
    service: Annotated[CollectionService, Depends(get_collection_service)],
) -> dict[str, str]:
    """Mount a collection.

    Args:
        request: Mount collection request
        service: Collection service instance

    Returns:
        Mount status

    Raises:
        HTTPException: 409 if already mounted, 400 for invalid source, 500 for other errors
    """
    try:
        return await service.mount_collection(request.identifier, request.source)
    except ValueError as exc:
        if "already mounted" in str(exc):
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to mount collection: {str(exc)}") from exc


@router.delete("/{identifier:path}", status_code=200)
async def unmount_collection(
    identifier: str,
    service: Annotated[CollectionService, Depends(get_collection_service)],
) -> dict[str, bool]:
    """Unmount a collection.

    Args:
        identifier: Collection identifier
        service: Collection service instance

    Returns:
        Unmount status

    Raises:
        HTTPException: 404 if collection not found, 500 for other errors
    """
    try:
        return await service.unmount_collection(identifier)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to unmount collection: {str(exc)}") from exc
