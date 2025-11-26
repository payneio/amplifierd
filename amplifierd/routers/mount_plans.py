"""Mount plan generation API endpoints."""

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from amplifier_library.storage import get_share_dir

from ..models.mount_plans import MountPlan
from ..models.mount_plans import MountPlanRequest
from ..services.mount_plan_service import MountPlanService
from ..services.profile_service import ProfileService
from .profiles import get_profile_service

router = APIRouter(prefix="/api/v1/mount-plans", tags=["mount-plans"])


def get_mount_plan_service(
    profile_service: Annotated[ProfileService, Depends(get_profile_service)],
) -> MountPlanService:
    """Get mount plan service instance.

    Args:
        profile_service: Profile service instance from dependency

    Returns:
        MountPlanService instance
    """
    share_dir = get_share_dir()
    return MountPlanService(
        profile_service=profile_service,
        share_dir=share_dir,
    )


@router.post("/generate", response_model=MountPlan, status_code=201)
async def generate_mount_plan(
    request: MountPlanRequest,
    service: Annotated[MountPlanService, Depends(get_mount_plan_service)],
) -> MountPlan:
    """Generate mount plan from cached profile.

    Creates a mount plan by resolving all resources from a cached profile.
    The mount plan contains all agents, context, and modules organized and
    ready for session initialization.

    Args:
        request: Mount plan request with profile_id and optional settings
        service: Mount plan service instance

    Returns:
        Complete mount plan with all resources mounted

    Raises:
        HTTPException:
            - 404 if profile not found
            - 400 if request is invalid
            - 500 for other errors

    Example:
        ```json
        {
            "profile_id": "foundation/base",
            "session_id": "my-session-123",
            "settings_overrides": {
                "llm": {"model": "gpt-4"}
            }
        }
        ```
    """
    try:
        return await service.generate_mount_plan(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate mount plan: {str(exc)}") from exc
