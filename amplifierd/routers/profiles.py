"""Profile management API endpoints."""

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from ..models import ProfileDetails
from ..models import ProfileInfo
from ..services import ProfileService

router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])


def get_profile_service() -> ProfileService:
    """Get profile service instance.

    Returns:
        ProfileService instance
    """
    return ProfileService()


@router.get("/", response_model=list[ProfileInfo])
async def list_profiles(
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> list[ProfileInfo]:
    """List all available profiles.

    Args:
        service: Profile service instance

    Returns:
        List of profile information
    """
    profiles = await service.list_profiles()
    return [ProfileInfo(**p) for p in profiles]  # pyright: ignore[reportArgumentType]


@router.get("/active", response_model=ProfileInfo | None)
async def get_active_profile(
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> ProfileInfo | None:
    """Get currently active profile.

    Args:
        service: Profile service instance

    Returns:
        Active profile information or None
    """
    profile = await service.get_active_profile()
    if profile is None:
        return None
    return ProfileInfo(**profile)  # pyright: ignore[reportArgumentType]


@router.get("/{name}", response_model=ProfileDetails)
async def get_profile(
    name: str,
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> ProfileDetails:
    """Get profile details by name.

    Args:
        name: Profile name
        service: Profile service instance

    Returns:
        Profile details

    Raises:
        HTTPException: 404 if profile not found, 500 for other errors
    """
    try:
        profile = await service.get_profile(name)
        return ProfileDetails(**profile)  # pyright: ignore[reportArgumentType]
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Profile not found: {name}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{name}/activate", status_code=200)
async def activate_profile(
    name: str,
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> dict[str, str]:
    """Activate a profile by name.

    Args:
        name: Profile name
        service: Profile service instance

    Returns:
        Activation status

    Raises:
        HTTPException: 404 if profile not found, 500 for other errors
    """
    try:
        return await service.activate_profile(name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to activate profile: {str(exc)}") from exc


@router.delete("/active", status_code=200)
async def deactivate_profile(
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> dict[str, bool]:
    """Deactivate the current profile.

    Args:
        service: Profile service instance

    Returns:
        Deactivation status

    Raises:
        HTTPException: 500 for errors
    """
    try:
        return await service.deactivate_profile()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to deactivate profile: {str(exc)}") from exc
