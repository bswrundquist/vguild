"""Infra-change orchestrator factory:
planner → infra-gcp → security → reviewer → qa → release-manager.
"""

from __future__ import annotations

from vguild.config import GatingConfig
from vguild.orchestrators.base import OrchestratorRunner
from vguild.registry import Registry
from vguild.run_store import RunStore
from vguild.sdk_adapter import SDKAdapter


def create_infra_change_runner(
    registry: Registry,
    adapter: SDKAdapter,
    store: RunStore,
    config: GatingConfig | None = None,
) -> OrchestratorRunner:
    """Return an OrchestratorRunner pre-loaded with the infra-change orchestrator."""
    orchestrator = registry.get_orchestrator("infra-change")
    return OrchestratorRunner(
        orchestrator=orchestrator,
        registry=registry,
        adapter=adapter,
        store=store,
        config=config,
    )
