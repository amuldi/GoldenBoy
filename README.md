# Golden Boy

![Golden Boy Mascot](assets/golden-boy.png)

> **Know the budget. Protect the result.**

Golden Boy is a budget-aware execution layer for AI coding agents.

---

## The Problem

You have 15% usage remaining. You submit a large coding task.

The agent starts normally. It spends the remaining budget on:
- Repository exploration
- Implementation
- Refactoring
- Testing
- Optional improvements

Then the budget runs out before the final result is returned. 

The problem isn't necessarily that the agent couldn't perform the task. The problem is that it failed to **adapt the task to the budget available**.

Golden Boy addresses this execution problem.

---

## Before & After

**BEFORE:**
Prompt → Agent starts → Analyze → Implement → Refactor → Test → **Budget exhausted** → Incomplete result

**AFTER:**
Prompt → Check budget → Estimate task → Assess risk → Adapt plan → Execute critical work → Validate → Checkpoint → **Return result**

---

## Core Idea: The Result-First Principle

Golden Boy prefers a smaller completed result over a larger unfinished task.

Never allow the agent to spend the remaining budget on low-priority improvements if doing so risks preventing a usable result from being returned.

## Checkpoints

Large tasks must be recoverable. If the budget becomes unsafe, Golden Boy saves the current state (a checkpoint). The next execution resumes from this checkpoint instead of restarting the entire task unnecessarily.

## Execution Modes

1. **SAFE**: Remaining budget is comfortably above estimated task cost. Normal execution.
2. **CAUTION**: Budget is sufficient but execution has some risk. Reduce unnecessary exploration.
3. **LIMITED**: Task is likely to exceed budget. Prioritize critical work, reduce scope, defer secondary work.
4. **CRITICAL**: Budget is almost exhausted. Finish current unit, save checkpoint, stop safely.

---

## Example

**Remaining budget:** `15%`

**User:**
> "Rebuild the entire dashboard UI, add responsive support, refactor the components, add animations, and run the complete test suite."

**Golden Boy Assessment:**
- Estimated requirement: `28%`
- Risk: **HIGH (LIMITED Mode)**

**Execution plan:**
- **P0** Dashboard structure
- **P1** Responsive layout
- **P2** Component cleanup
- **P3** Animations
- **P4** Full test suite

**Execute:**
- [x] Dashboard structure
- [x] Responsive layout
- [x] Basic validation

**Deferred:**
- [ ] Component cleanup
- [ ] Animations
- [ ] Full test suite

**Result:**
> "Core dashboard redesign completed. 3 optional tasks deferred. Checkpoint saved."

---

## Architecture

Golden Boy is designed around a provider-agnostic architecture:
- **Provider Adapters**: Normalize available usage info.
- **Task Estimator**: Predicts cost probabilistically.
- **Risk Engine**: Determines Execution Mode.
- **Adaptive Executor**: Executes and checkpoints based on priority.

## Installation

```bash
pip install -e .
```

## Usage & Commands

Use the CLI to interact with Golden Boy's execution layer:

- **`goldenboy status`**
  Show remaining budget, usable budget (after safety margin), and pending checkpoints.

- **`goldenboy plan <task>`**
  Analyze the current task and show the planned execution strategy.

- **`goldenboy run <task>`**
  Execute the task adaptively based on the available budget.

- **`goldenboy resume`**
  Resume execution from the previous checkpoint.

---

## Limitations

- **Estimation is probabilistic**: Exact future token consumption cannot always be predicted.
- **Provider support varies**: Providers expose different usage information. Quota and token limits are different concepts.
- **No guarantees**: Golden Boy cannot guarantee that a task will finish within a budget, but it will fail safely when budget information is unavailable.

## Roadmap

- [x] Core Risk and Estimation Engine
- [x] Checkpoint System
- [x] Mock Provider for testing
- [ ] OpenAI Provider Adapter
- [ ] Anthropic Provider Adapter
- [ ] DeepMind Provider Adapter

## Contributing
Contributions are welcome. Please read `CONTRIBUTING.md` (coming soon) for details on our code of conduct, and the process for submitting pull requests to us.

## License
MIT License
