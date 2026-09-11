<p align="center">
  <picture>
    <img src="assets/golden-boy.png" width="220" alt="Golden Boy, the budget master">
  </picture>
</p>

<h1 align="center">Golden Boy</h1>

<p align="center">
  <em>Know the budget. Protect the result.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/execution-budget--aware-111111?style=flat-square" alt="Budget Aware">
  <img src="https://img.shields.io/badge/works%20with-any%20agent-111111?style=flat-square" alt="Works with any agent">
  <img src="https://img.shields.io/badge/license-MIT-111111?style=flat-square" alt="MIT license">
</p>

<p align="center">
  <strong>Guarantees results before the budget runs out &middot; 100% recoverable &middot; adaptive execution</strong><br>
  <sub>Measured on large AI coding tasks where agents typically run out of quota mid-task. Golden Boy adapts the execution plan to available budget, prioritizing critical features and cleanly deferring optional polish. The result is a usable, working product instead of a broken, half-finished repository.</sub>
</p>

---

You have 15% usage remaining. You submit a large coding task.

The agent starts normally. It spends the remaining budget on repository exploration, implementation, refactoring, testing, and optional improvements. 

Then the budget runs out before the final result is returned. 

The problem isn't necessarily that the agent couldn't perform the task. The problem is that it failed to **adapt the task to the budget available**.

Golden Boy puts a budget-aware execution layer inside your AI agent.

## Before / after

You ask an agent to rebuild the entire dashboard UI, add responsive support, refactor components, and run the test suite.

Without Golden Boy:

Prompt → Agent starts → Analyze → Implement → Refactor → Test → **Budget exhausted** → Incomplete, broken result.

With Golden Boy:

Prompt → Check budget → Estimate task → Assess risk → Adapt plan → Execute critical work → Validate → Checkpoint → **Return working result**.

> "Core dashboard redesign completed. 3 optional tasks deferred. Checkpoint saved."

## The Result-First Principle

**The rule is never "use fewest tokens."** It is: maximize completed, useful work within the remaining budget.

Golden Boy prefers a smaller completed result over a larger unfinished task. It never allows the agent to spend the remaining budget on low-priority improvements if doing so risks preventing a usable result from being returned.

## Execution Modes

Golden Boy dynamically assesses risk and switches modes:

1. **SAFE**: Remaining budget is comfortably above estimated task cost. Normal execution.
2. **CAUTION**: Budget is sufficient but execution has some risk. Reduce unnecessary exploration.
3. **LIMITED**: Task is likely to exceed budget. Prioritize critical work, reduce scope, defer secondary work.
4. **CRITICAL**: Budget is almost exhausted. Finish current unit, save checkpoint, stop safely.

## Checkpoints

Large tasks must be recoverable. If the budget becomes unsafe, Golden Boy saves the current state (a checkpoint). The next execution resumes from this checkpoint instead of restarting the entire task unnecessarily.

## Architecture

Golden Boy is designed around a provider-agnostic architecture:
- **Provider Adapters**: Normalize available usage info across providers (Claude, OpenAI, etc.).
- **Task Estimator**: Predicts cost probabilistically.
- **Risk Engine**: Determines Execution Mode.
- **Adaptive Executor**: Executes and checkpoints based on priority.

## Install

Golden Boy installs as a standard Python package.

```bash
pip install -e .
```

## Commands

Use the CLI to interact with Golden Boy's execution layer:

| Command | What it does |
|---------|--------------|
| `goldenboy status` | Show remaining budget, usable budget (after safety margin), and pending checkpoints. |
| `goldenboy plan <task>` | Analyze the current task and show the planned execution strategy based on risk. |
| `goldenboy run <task>` | Execute the task adaptively based on the available budget. |
| `goldenboy resume` | Resume execution from the previous checkpoint. |

*(Note: Provide a `--budget` flag to mock available quota during testing.)*

## Limitations

- **Estimation is probabilistic**: Exact future token consumption cannot always be predicted.
- **Provider support varies**: Providers expose different usage information. Quota and token limits are different concepts.
- **No guarantees**: Golden Boy cannot guarantee that a task will finish within a budget, but it will fail safely when budget information is unavailable.

## License

[MIT](LICENSE). The shortest license that works.
