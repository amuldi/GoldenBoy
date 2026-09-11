import argparse
import sys
from goldenboy.core.priorities import Priority, ExecutionUnit
from goldenboy.adapters.mock import MockProvider
from goldenboy.core.executor import AdaptiveExecutor
from goldenboy.core.estimator import Estimator
from goldenboy.core.risk import RiskEngine

def create_mock_plan():
    return [
        ExecutionUnit("1", "Dashboard structure", Priority.P0, estimated_cost=10.0),
        ExecutionUnit("2", "Responsive layout", Priority.P1, estimated_cost=8.0),
        ExecutionUnit("3", "Component cleanup", Priority.P2, estimated_cost=5.0),
        ExecutionUnit("4", "Animations", Priority.P3, estimated_cost=4.0),
        ExecutionUnit("5", "Full test suite", Priority.P4, estimated_cost=6.0),
    ]

def status_cmd(args):
    provider = MockProvider(initial_percentage=args.budget)
    budget = provider.get_available_budget()
    
    print("--- Golden Boy Status ---")
    print(f"Remaining Budget: {budget.remaining_percentage}%")
    if budget.is_exhausted():
        print("State: EXHAUSTED (Below safety margin)")
    else:
        print(f"Usable Budget:    {budget.usable_percentage}%")
        
    # Check if there's a checkpoint
    from goldenboy.core.checkpoint import CheckpointManager
    cm = CheckpointManager()
    cp = cm.load()
    if cp:
        print(f"\nCheckpoint found for task: '{cp['task_name']}'")
        deferred = [u for u in cp['plan'] if u.status == "deferred"]
        print(f"Deferred units: {len(deferred)}")

def plan_cmd(args):
    provider = MockProvider(initial_percentage=args.budget)
    budget = provider.get_available_budget()
    
    plan = create_mock_plan()
    estimator = Estimator()
    estimate = estimator.estimate_plan(plan)
    
    risk_engine = RiskEngine()
    mode = risk_engine.assess(budget, estimate)
    
    print("--- Execution Plan ---")
    print(f"Budget: {budget.remaining_percentage}%")
    print(f"Estimated Cost: {estimate.estimated_percentage}%")
    print(f"Risk Assessment: {mode.name}\n")
    
    print("Planned Execution:")
    for unit in plan:
        print(f"  [{unit.priority.name}] {unit.description} (Cost: {unit.estimated_cost}%)")

def run_cmd(args):
    provider = MockProvider(initial_percentage=args.budget)
    executor = AdaptiveExecutor(provider)
    
    plan = create_mock_plan()
    
    print(f"Starting Task: '{args.task}'")
    result_msg, final_plan = executor.execute(args.task, plan)
    
    print("\n--- Result ---")
    print(result_msg)
    print("\nDeferred Work:")
    deferred = [u for u in final_plan if u.status == "deferred"]
    if not deferred:
        print("  None.")
    for d in deferred:
        print(f"  - [{d.priority.name}] {d.description}")

def resume_cmd(args):
    provider = MockProvider(initial_percentage=args.budget)
    executor = AdaptiveExecutor(provider)
    
    from goldenboy.core.checkpoint import CheckpointManager
    cm = CheckpointManager()
    state = cm.load()
    
    if not state:
        print("No checkpoint found.")
        return
        
    task_name = state['task_name']
    plan = state['plan']
    
    # Reset deferred tasks to pending for resume
    for unit in plan:
        if unit.status == "deferred":
            unit.status = "pending"
            
    print(f"Resuming Task: '{task_name}'")
    result_msg, final_plan = executor.execute(task_name, plan)
    
    print("\n--- Resume Result ---")
    print(result_msg)


def main():
    parser = argparse.ArgumentParser(description="Golden Boy - Budget-Aware Execution Layer")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Status
    p_status = subparsers.add_parser("status", help="Show current budget state and risk")
    p_status.add_argument("--budget", type=float, default=100.0, help="Mock starting budget")
    
    # Plan
    p_plan = subparsers.add_parser("plan", help="Analyze task and show execution strategy")
    p_plan.add_argument("task", type=str, help="The task to analyze")
    p_plan.add_argument("--budget", type=float, default=100.0, help="Mock starting budget")
    
    # Run
    p_run = subparsers.add_parser("run", help="Execute a task adaptively")
    p_run.add_argument("task", type=str, help="The task to execute")
    p_run.add_argument("--budget", type=float, default=100.0, help="Mock starting budget")
    
    # Resume
    p_resume = subparsers.add_parser("resume", help="Resume the previous checkpoint")
    p_resume.add_argument("--budget", type=float, default=100.0, help="Mock starting budget")

    args = parser.parse_args()
    
    if args.command == "status":
        status_cmd(args)
    elif args.command == "plan":
        plan_cmd(args)
    elif args.command == "run":
        run_cmd(args)
    elif args.command == "resume":
        resume_cmd(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
