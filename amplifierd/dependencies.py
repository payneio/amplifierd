"""Shared dependency factories for FastAPI endpoints.

These factories provide dependency injection for service instances,
ensuring proper initialization and resource management.
"""

from amplifier_library.cache import ChangeDetectionService
from amplifier_library.cache import MetadataStore
from amplifier_library.cache import StatusService
from amplifier_library.cache import UpdateService
from amplifier_library.storage import get_share_dir
from amplifier_library.storage import get_state_dir
from amplifier_library.storage.paths import get_profiles_dir

from .services.collection_service import CollectionService
from .services.profile_compilation import ProfileCompilationService
from .services.profile_discovery import ProfileDiscoveryService
from .services.ref_resolution import RefResolutionService


def get_metadata_store() -> MetadataStore:
    """Get metadata store instance.

    Returns:
        MetadataStore instance
    """
    return MetadataStore()


def get_ref_resolution_service() -> RefResolutionService:
    """Get reference resolution service.

    Returns:
        RefResolutionService instance
    """
    state_dir = get_state_dir()
    return RefResolutionService(state_dir=state_dir)


def get_profile_discovery_service() -> ProfileDiscoveryService:
    """Get profile discovery service.

    Returns:
        ProfileDiscoveryService instance
    """
    cache_dir = get_profiles_dir()
    return ProfileDiscoveryService(cache_dir=cache_dir)


def get_profile_compilation_service() -> ProfileCompilationService:
    """Get profile compilation service.

    Returns:
        ProfileCompilationService instance
    """
    share_dir = get_share_dir()
    ref_resolution = get_ref_resolution_service()
    return ProfileCompilationService(
        share_dir=share_dir,
        ref_resolution=ref_resolution,
    )


def get_collection_service() -> CollectionService:
    """Get collection service.

    Returns:
        CollectionService instance
    """
    share_dir = get_share_dir()
    discovery_service = get_profile_discovery_service()
    compilation_service = get_profile_compilation_service()

    return CollectionService(
        share_dir=share_dir,
        discovery_service=discovery_service,
        compilation_service=compilation_service,
    )


def get_change_detection_service() -> ChangeDetectionService:
    """Get change detection service.

    Returns:
        ChangeDetectionService instance
    """
    metadata_store = get_metadata_store()
    ref_resolution = get_ref_resolution_service()
    return ChangeDetectionService(
        metadata_store=metadata_store,
        ref_resolution_service=ref_resolution,
    )


def get_status_service() -> StatusService:
    """Get status service.

    Returns:
        StatusService instance
    """
    metadata_store = get_metadata_store()
    return StatusService(metadata_store=metadata_store)


def get_update_service() -> UpdateService:
    """Get update service with all dependencies.

    Returns:
        UpdateService instance
    """
    metadata_store = get_metadata_store()
    change_detection = get_change_detection_service()
    collection_service = get_collection_service()
    ref_resolution_service = get_ref_resolution_service()
    profile_discovery_service = get_profile_discovery_service()
    profile_compilation_service = get_profile_compilation_service()

    return UpdateService(
        metadata_store=metadata_store,
        change_detection=change_detection,
        collection_service=collection_service,
        ref_resolution_service=ref_resolution_service,
        profile_discovery_service=profile_discovery_service,
        profile_compilation_service=profile_compilation_service,
    )
