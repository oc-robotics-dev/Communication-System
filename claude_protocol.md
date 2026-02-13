# Claude Protocol – Galaxy RVR

Rules for how the coding agent should work in this repository.

---

## 1. Source of Truth

The following docs are canonical. Never contradict them; propose edits instead.

| Doc | Purpose |
|-----|---------|
| `VISION.md` | Project goals and high-level architecture |
| `implementation_plan.md` | Current implementation roadmap |
| `TASKS.md` | Active task list and priorities |
| `TESTING.md` | Test strategy, directory layout, and commands |

## 2. Starting a Task

1. **Read only the relevant sections** of the docs above (don't dump the whole file).
2. **Summarise context in 3 bullets** before writing any code:
   - What the feature/fix is and why it matters.
   - Which packages/files are affected.
   - Any open questions or unknowns.

## 3. Plan → Approve → Implement

1. Propose a **3–6 step plan** in a numbered list.
2. **Wait for explicit approval** before touching any code.
3. Implement **one step at a time** with small, reviewable diffs.
4. After each step, summarise what changed and what's next.

## 4. Tests & Quality

After every code change:

- **Add or update tests** that cover the change.
- **Run the test + lint commands** from `TESTING.md`, or state the exact commands for the user to run:
  ```bash
  # ROS 2 tests (from ros2_ws/)
  colcon test --event-handlers console_cohesion+
  colcon test-result --verbose

  # Python lint
  flake8 ros2_ws/src/galaxy_rvr_controller/galaxy_rvr_controller/

  # Arduino syntax check (from arduino_ws/)
  arduino-cli compile --fqbn arduino:avr:uno roverGalaxyDriver
  ```
- Report pass/fail results before moving to the next step.

## 5. Keep Docs in Sync

- If a code change affects scope, architecture, or task status, **propose minimal edits** to `VISION.md`, `implementation_plan.md`, `TASKS.md`, or `TESTING.md`.
- Present doc edits as diffs for approval.

## 6. No Guessing

- **Never invent** external APIs, hardware specs, pin assignments, or protocol details.
- If something is not defined in the docs or codebase, **ask the user** before proceeding.

## 7. General Guidelines

- Keep diffs minimal; avoid unrelated refactors in the same change.
- Use the project's existing code style and naming conventions.
- Prefer editing existing files over creating new ones when reasonable.
- When uncertain between two approaches, present both and let the user choose.
