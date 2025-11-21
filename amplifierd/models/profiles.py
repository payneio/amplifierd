"""API models for profile operations."""

from pydantic import BaseModel
from pydantic import Field


class ProfileInfo(BaseModel):
    """Basic profile information."""

    name: str = Field(description="Profile name")
    source: str = Field(description="Profile source (user, project, collection)")
    is_active: bool = Field(description="Whether this profile is currently active")


class ModuleConfig(BaseModel):
    """Module configuration in a profile."""

    module: str = Field(description="Module identifier")
    source: str | None = Field(default=None, description="Module source URL or path")
    config: dict[str, object] | None = Field(default=None, description="Module configuration")


class ProfileDetails(BaseModel):
    """Detailed profile information."""

    name: str = Field(description="Profile name")
    version: str = Field(description="Profile version")
    description: str = Field(description="Profile description")
    source: str = Field(description="Profile source (user, project, collection)")
    is_active: bool = Field(description="Whether this profile is currently active")
    inheritance_chain: list[str] = Field(description="Profile inheritance chain")
    providers: list[ModuleConfig] = Field(description="Provider modules")
    tools: list[ModuleConfig] = Field(description="Tool modules")
    hooks: list[ModuleConfig] = Field(description="Hook modules")
