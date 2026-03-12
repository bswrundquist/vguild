"""Runtime configuration for vguild."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class GatingConfig(BaseModel):
    """Quality gate parameters — can be overridden via CLI flags."""

    min_quality: int = Field(default=8, ge=0, le=10, description="Minimum quality score to pass")
    max_rounds: int = Field(default=10, ge=1, description="Maximum orchestrator rounds")
    max_no_progress: int = Field(
        default=2, ge=1, description="Max consecutive rounds without quality improvement"
    )
    fail_on_blocked: bool = Field(
        default=False, description="Treat blocked status as a hard failure"
    )


class VGuildConfig(BaseModel):
    """Top-level runtime configuration."""

    catalog_dir: Path = Field(default=Path("catalog"), description="Catalog root directory")
    runs_dir: Path = Field(default=Path("runs"), description="Run artifact storage directory")
    gating: GatingConfig = Field(default_factory=GatingConfig)

    model_config = {"arbitrary_types_allowed": True}
