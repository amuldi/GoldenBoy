import logging
from typing import List, Optional, Tuple

from goldenboy.core.budget import Budget
from goldenboy.core.checkpoint import CheckpointManager
from goldenboy.core.config import GoldenBoyConfig, get_default_config
from goldenboy.core.estimator import Estimator, TaskEstimate
from goldenboy.core.priorities import ExecutionUnit, Priority
from goldenboy.core.risk import ExecutionMode, RiskEngine

logger = logging.getLogger("goldenboy.executor")


class AdaptiveExecutor:
    """The core engine that adapts execution based on budget constraints.

    This class does not perform coding work itself — `execute()` drives a
    plan of `ExecutionUnit`s through a provider that can genuinely execute
    them (in practice, `MockProvider`, for demos/tests). For real work,
    prefer `assess()` plus your own callable via
    `goldenboy.integration.budget_aware_execution`, which shares this same
    assess-then-adapt decision path instead of reimplementing it.
    """

    def __init__(self, provider_adapter, config: Optional[GoldenBoyConfig] = None):
        self.provider = provider_adapter
        self.config = config or get_default_config()
        self.estimator = Estimator(config=self.config)
        self.risk_engine = RiskEngine(config=self.config)
        self.checkpointer = CheckpointManager()

    def assess(self, plan: List[ExecutionUnit]) -> Tuple[Budget, TaskEstimate, ExecutionMode]:
        """Single source of truth for "given this plan and the provider's
        current budget, what's the risk and what should happen?" — shared
        by `execute()` and `integration.budget_aware_execution` so the two
        entry points can't drift into different decisions for the same
        inputs.
        """
        budget = self.provider.get_available_budget()
        estimate = self.estimator.estimate_plan(plan)
        mode = self.risk_engine.assess(budget, estimate)
        return budget, estimate, mode

    def adapt_plan(self, plan: List[ExecutionUnit], mode: ExecutionMode) -> List[ExecutionUnit]:
        """Modifies the plan based on the execution mode."""
        if mode in (ExecutionMode.SAFE, ExecutionMode.CAUTION):
            # Try to execute everything, maybe with caution
            return plan

        elif mode == ExecutionMode.LIMITED:
            # Defer P3 and P4 tasks
            for unit in plan:
                if unit.priority in (Priority.P3, Priority.P4) and unit.status == "pending":
                    unit.defer()
            return plan

        elif mode == ExecutionMode.CRITICAL:
            # Defer everything except P0
            for unit in plan:
                if unit.priority != Priority.P0 and unit.status == "pending":
                    unit.defer()
            return plan

        return plan

    def execute(self, task_name: str, plan: List[ExecutionUnit]) -> Tuple[str, List[ExecutionUnit]]:
        """Executes the plan adaptively.

        Requires a provider whose `execute_unit` genuinely performs each
        unit (see `ProviderAdapter.execute_unit`) — real LLM-usage adapters
        will raise NotImplementedError here by design; use the
        `budget_aware_execution` decorator with those instead.
        """
        budget, estimate, mode = self.assess(plan)
        logger.info("[%s] Budget: %.2f%% | Risk: %s", task_name, budget.remaining_percentage, mode.name)

        adapted_plan = self.adapt_plan(plan, mode)

        for unit in adapted_plan:
            if unit.status in ("deferred", "completed"):
                continue

            logger.info("  -> Executing: [%s] %s", unit.priority.name, unit.description)
            success = self.provider.execute_unit(unit)

            if success:
                unit.complete()
            else:
                unit.defer()

            # Re-evaluate budget after each unit
            current_budget = self.provider.get_available_budget()
            if current_budget.is_exhausted():
                logger.warning("Budget critically low. Triggering graceful stop.")
                for u in adapted_plan:
                    if u.status == "pending":
                        u.defer()
                break

        final_deferred = [u for u in adapted_plan if u.status == "deferred"]
        final_completed = [u for u in adapted_plan if u.status == "completed"]

        if final_deferred:
            logger.info("Saving checkpoint for deferred work.")
            self.checkpointer.save(task_name, adapted_plan, mode.name, budget=budget)
        else:
            self.checkpointer.clear()

        result_msg = (
            f"Task '{task_name}' finished. "
            f"Completed {len(final_completed)} units. Deferred {len(final_deferred)} units."
        )
        return result_msg, adapted_plan
