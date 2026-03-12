"""New-feature orchestrator factory:
planner → implementer → maintainer → reviewer → qa → release-manager.
"""

from __future__ import annotations

from vguild.config import GatingConfig
from vguild.orchestrators.base import OrchestratorRunner
from vguild.registry import Registry
from vguild.run_store import RunStore
from vguild.sdk_adapter import SDKAdapter


def create_new_feature_runner(
    registry: Registry,
    adapter: SDKAdapter,
    store: RunStore,
    config: GatingConfig | None = None,
) -> OrchestratorRunner:
    """Return an OrchestratorRunner pre-loaded with the new-feature orchestrator."""
    orchestrator = registry.get_orchestrator("new-feature")
    return OrchestratorRunner(
        orchestrator=orchestrator,
        registry=registry,
        adapter=adapter,
        store=store,
        config=config,
    )
