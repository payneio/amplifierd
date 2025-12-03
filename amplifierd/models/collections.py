"""API models for collection operations."""

from pydantic import Field

from amplifierd.models.base import CamelCaseModel


class ProfileManifest(CamelCaseModel):
    """Reference to a profile in a collection."""

    name: str = Field(description="Profile name")
    version: str = Field(description="Profile version")
    path: str = Field(description="Relative path in collection")
    installed_at: str | None = Field(default=None, description="ISO timestamp when profile was fetched/compiled")


class CollectionInfo(CamelCaseModel):
    """Collection information - a set of profile manifests."""

    identifier: str = Field(description="Collection identifier")
    source: str = Field(description="Collection source reference")
    profiles: list[ProfileManifest] = Field(default_factory=list, description="Profile manifests in collection")


class ComponentRef(CamelCaseModel):
    """Reference to a component with profile context."""

    profile: str = Field(description="Profile identifier in format 'collection/profile-id'")
    name: str = Field(description="Component module name")
    uri: str = Field(description="Component source URI (git or fsspec format)")


class ComponentRefsResponse(CamelCaseModel):
    """All component references across all profiles."""

    orchestrators: list[ComponentRef] = Field(default_factory=list)
    context_managers: list[ComponentRef] = Field(default_factory=list)
    providers: list[ComponentRef] = Field(default_factory=list)
    tools: list[ComponentRef] = Field(default_factory=list)
    hooks: list[ComponentRef] = Field(default_factory=list)
    agents: list[ComponentRef] = Field(default_factory=list)
    contexts: list[ComponentRef] = Field(default_factory=list)
